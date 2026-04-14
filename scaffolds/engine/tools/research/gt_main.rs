use clap::{Parser, Subcommand};
use gametorch::animations;
use serde_json;
use std::env;

/// Return the list of durations supported by a given animation model name.
/// This is a hard-coded map intended to smooth UX; the backend is the ultimate source of truth.
fn supported_durations(model_name: &str) -> Option<&'static [u32]> {
    match model_name {
        "beta/v1.1" | "beta/v1.2" | "beta/v1.3" |
        "alpha/v1.1" | "alpha/v1.2" | "alpha/v2.1" | "alpha/v2.2" => Some(&[5, 10]),
        "beta/v1.4" => Some(&[6]),
        "gamma/v1.1" | "gamma/v1.2" => Some(&[8]),
        _ => None,
    }
}

/// GameTorch command-line interface.
///
/// This binary provides access to GameTorch functionality via the `gametorch` command.
/// Your API key is loaded from the `GAMETORCH_API_KEY` environment variable.
#[derive(Parser)]
#[command(name = "gametorch")]
#[command(author, version, about, long_about = None)]
pub struct Cli {
    /// Use local server (http://localhost:8000) instead of production.
    #[arg(short = 'l', long = "local", global = true)]
    local: bool,
    /// Output raw computer-friendly JSON (no human status replacement)
    #[arg(short = 'p', long = "porcelain", global = true)]
    porcelain: bool,
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
pub enum Commands {
    /// Animation-related operations
    Animations {
        #[command(subcommand)]
        action: AnimationCommands,
    },
}

#[derive(Subcommand)]
pub enum AnimationCommands {
    /// Retrieve an existing animation
    Get {
        /// The identifier of the animation to fetch (omit to list all animations)
        id: Option<String>,
    },
    /// List available animation models and their details
    Models,
    /// Generate a new animation
    Generate {
        /// The prompt or parameters used for generation
        prompt: String,
        /// Block until rendering finishes and download ZIP.
        #[arg(short = 'b', long = "block")]
        block: bool,
        /// Output file for the resulting ZIP when using --block.
        #[arg(short = 'o', long = "output-file")]
        output_file: Option<String>,
        /// Input image file path (required)
        #[arg(short = 'i', long = "input-image", value_name = "FILE")]
        input_image: String,
        /// Optional animation model ID (defaults to 9)
        #[arg(long = "model-id", value_name = "ID", conflicts_with = "model_name")]
        model_id: Option<u32>,
        /// Optional animation model name (defaults to 'gamma/v1.1')
        #[arg(long = "model-name", value_name = "NAME", conflicts_with = "model_id")]
        model_name: Option<String>,
        /// Suppress informational logs
        #[arg(short = 's', long = "silent")]
        silent: bool,
        /// Duration in seconds (backend-supported values, defaults to 5)
        #[arg(short = 'd', long = "duration", value_name = "SECONDS", default_value_t = 5)]
        duration: u32,
    },
    /// Display instructions for cropping an animation result
    Crop {
        /// (Optional) Animation result ID. If omitted, prints general instructions.
        animation_result_id: Option<String>,
    },
    /// Regenerate an animation (note: this takes an animation_id, **not** an animation_result_id)
    Regenerate {
        /// The identifier of the animation to regenerate
        animation_id: String,
    },
}

#[tokio::main]
async fn main() {
    // Parse CLI arguments
    let cli = Cli::parse();

    // Retrieve API key from environment variable
    let api_key = env::var("GAMETORCH_API_KEY").unwrap_or_else(|_| {
        eprintln!(
            "Error: environment variable GAMETORCH_API_KEY not set.\n\
            Please set it before using this CLI."
        );
        std::process::exit(1);
    });

    // Determine base URL depending on --local flag
    let base_url = if cli.local {
        "http://localhost:8000"
    } else {
        "https://gametorch.app"
    };

    // Helper to map numeric status to human string.
    fn replace_status_recursive(value: &mut serde_json::Value) {
        use serde_json::Value;
        match value {
            Value::Object(map) => {
                if let Some(status_val) = map.get_mut("status") {
                    if let Some(num) = status_val.as_i64() {
                        let new_str = match num {
                            1 => "generating",
                            2 => "complete",
                            3 => "failed and refunded",
                            _ => return,
                        };
                        *status_val = Value::String(new_str.to_string());
                    }
                }
                for v in map.values_mut() {
                    replace_status_recursive(v);
                }
            }
            Value::Array(arr) => {
                for v in arr {
                    replace_status_recursive(v);
                }
            }
            _ => {}
        }
    }

    // Dispatch based on the parsed commands
    match cli.command {
        Commands::Animations { action } => match action {
            AnimationCommands::Get { id } => {
                if let Some(id) = id {
                    match animations::get(&api_key, base_url, &id).await {
                        Ok(mut json) => {
                            if !cli.porcelain {
                                replace_status_recursive(&mut json);
                            }
                            println!("{}", serde_json::to_string_pretty(&json).unwrap());
                        }
                        Err(err) => {
                            eprintln!("Failed to fetch animation: {}", err);
                            std::process::exit(1);
                        }
                    }
                } else {
                    match animations::list(&api_key, base_url).await {
                        Ok(mut json) => {
                            if !cli.porcelain {
                                replace_status_recursive(&mut json);
                            }
                            println!("{}", serde_json::to_string_pretty(&json).unwrap());
                        }
                        Err(err) => {
                            eprintln!("Failed to list animations: {}", err);
                            std::process::exit(1);
                        }
                    }
                    // Apply human-readable status mapping for list as well
                    if !cli.porcelain {
                        // After successful listing above, json is already printed
                        // We handled inside Ok branch before printing.
                    }
                }
            }
            AnimationCommands::Models => {
                match animations::models(&api_key, base_url).await {
                    Ok(json) => {
                        println!("{}", serde_json::to_string_pretty(&json).unwrap());
                    }
                    Err(err) => {
                        eprintln!("Failed to fetch models: {}", err);
                        std::process::exit(1);
                    }
                }
            }
            AnimationCommands::Generate { prompt, block, output_file, input_image, model_id, mut model_name, silent, mut duration } => {
                // Adjust duration to closest valid one if we can determine supported list.
                if let Some(name) = model_name.as_deref() {
                    if let Some(supported) = supported_durations(name) {
                        // Find closest duration (absolute difference, tie -> lower value).
                        let closest = *supported.iter().min_by_key(|d| (i32::abs(**d as i32 - duration as i32), **d)).unwrap();
                        if closest != duration {
                            eprintln!("Note: duration {} is not supported by model '{}'. Using {} seconds instead.", duration, name, closest);
                            duration = closest;
                        }
                    }
                }

                // Apply default model name if neither id nor name supplied
                let model_id = model_id; // keep immutable shadowing
                if model_id.is_none() && model_name.is_none() {
                    model_name = Some("gamma/v1.1".to_string());
                }

                if let Some(name) = model_name.as_deref() {
                    if let Some(supported) = supported_durations(name) {
                        // Find closest duration (absolute difference, tie -> lower value).
                        let closest = *supported.iter().min_by_key(|d| (i32::abs(**d as i32 - duration as i32), **d)).unwrap();
                        if closest != duration {
                            eprintln!("Note: duration {} is not supported by model '{}'. Using {} seconds instead.", duration, name, closest);
                            duration = closest;
                        }
                    }
                }

                match animations::generate(&api_key, base_url, &prompt, duration, block, output_file.as_deref(), Some(&input_image), model_id, model_name.as_deref(), silent).await {
                    Ok(mut json) => {
                        if !cli.porcelain {
                            replace_status_recursive(&mut json);
                        }
                        println!("{}", serde_json::to_string_pretty(&json).unwrap());
                    }
                    Err(err) => {
                        eprintln!("Failed to generate animation: {}", err);
                        std::process::exit(1);
                    }
                }
            }
            AnimationCommands::Crop { animation_result_id } => {
                match animation_result_id {
                    Some(id) => {
                        println!(
                            "Open this page in your browser: https://gametorch.app/sprite-animator/crop-and-trim/{}",
                            id
                        );
                    }
                    None => {
                        println!(
                            "Cropping is only available through the GameTorch web UI.\n");
                        println!(
                            "1. Open this link in your browser: https://gametorch.app/sprite-animator.\n2. Select the animation that contains the desired result.\n3. Choose the specific animation result and click \"Crop & Trim\".\n",
                        );
                    }
                }
            }
            AnimationCommands::Regenerate { animation_id } => {
                match animations::regenerate(&api_key, base_url, &animation_id).await {
                    Ok(json) => {
                        println!("{}", serde_json::to_string_pretty(&json).unwrap());
                    }
                    Err(err) => {
                        eprintln!("Failed to regenerate animation: {}", err);
                        std::process::exit(1);
                    }
                }
            }
        },
    }
}
