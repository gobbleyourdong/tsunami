//! GameTorch library crate.
//!
//! This crate will expose reusable APIs that power the `gametorch` CLI.
//! Functionality will be filled in as development progresses.

pub mod animations {
    use serde_json::Value;
    use reqwest;
    use base64::{engine::general_purpose, Engine as _};

    /// Fetch animation results for a given animation.
    ///
    /// Hits `GET /api/animation_results/<animation_id>` and returns the JSON as-is
    /// (array or object depending on backend version).
    pub async fn get(
        api_key: &str,
        base_url: &str,
        animation_id: &str,
    ) -> Result<Value, Box<dyn std::error::Error + Send + Sync>> {
        let client = reqwest::Client::new();

        let url = format!("{}/api/animation_results/{}", base_url, animation_id);
        let json: Value = client
            .get(&url)
            .header("Authorization", format!("Bearer {}", api_key))
            .send()
            .await?
            .error_for_status()?
            .json()
            .await?;

        Ok(json)
    }

    /// List all animations belonging to the current user.
    pub async fn list(
        api_key: &str,
        base_url: &str,
    ) -> Result<Value, Box<dyn std::error::Error + Send + Sync>> {
        let client = reqwest::Client::new();

        let url = format!("{}/api/animations", base_url);
        let animations: Value = client
            .get(&url)
            .header("Authorization", format!("Bearer {}", api_key))
            .send()
            .await?
            .error_for_status()?
            .json()
            .await?;

        Ok(animations)
    }

    /// Generate a new animation from a prompt.
    ///
    /// Returns a JSON object of shape:
    /// `{ "animation_id": ..., "result_id": ..., "zip_path": ... }`.
    pub async fn generate(
        api_key: &str,
        base_url: &str,
        prompt: &str,
        duration_seconds: u32,
        block: bool,
        output_file: Option<&str>,
        input_image_path: Option<&str>,
        model_id: Option<u32>,
        model_name: Option<&str>,
        silent: bool,
    ) -> Result<Value, Box<dyn std::error::Error + Send + Sync>> {
        // No local duration validation; let the backend validate and return any errors.

        let client = reqwest::Client::new();

        // Validate mutually exclusive parameters (should already be handled by CLI)
        if model_id.is_some() && model_name.is_some() {
            return Err("Specify either model_id or model_name, not both".into());
        }

        if !silent {
            println!("Starting animation generation request...");
        }

        // Prepare input_image_base64 if provided
        let input_image_base64 = if let Some(path) = input_image_path {
            let bytes = tokio::fs::read(path).await?;
            general_purpose::STANDARD.encode(bytes)
        } else {
            String::new()
        };

        // Build request body dynamically
        let mut body_map = serde_json::Map::new();
        body_map.insert("prompt".to_string(), serde_json::Value::String(prompt.to_string()));
        body_map.insert("duration_seconds".to_string(), serde_json::Value::Number(duration_seconds.into()));
        body_map.insert(
            "input_image_base64".to_string(),
            serde_json::Value::String(input_image_base64),
        );

        match (model_id, model_name) {
            (Some(id), None) => {
                body_map.insert(
                    "animation_model_id".to_string(),
                    serde_json::Value::Number(id.into()),
                );
            }
            (None, Some(name)) => {
                body_map.insert(
                    "animation_model_name".to_string(),
                    serde_json::Value::String(name.to_string()),
                );
            }
            (None, None) => {
                // default to id 9
                body_map.insert(
                    "animation_model_id".to_string(),
                    serde_json::Value::Number(9.into()),
                );
            }
            _ => unreachable!(),
        }

        let body = serde_json::Value::Object(body_map);

        let post_url = format!("{}/api/animation", base_url);
        let resp = client
            .post(&post_url)
            .header("Authorization", format!("Bearer {}", api_key))
            .json(&body)
            .send()
            .await?;

        if !resp.status().is_success() {
            // Try to read full body text for better error visibility.
            let status = resp.status();
            let text = resp.text().await.unwrap_or_else(|_| "<failed to read body>".to_string());
            return Err(format!("request failed (HTTP {}): {}", status, text).into());
        }

        let post_resp: Value = resp.json().await?;

        let animation_id = post_resp
            .get("animation_id")
            .and_then(|v| v.as_i64())
            .ok_or("animation_id missing from response")?;

        if !silent {
            println!("Animation created successfully (ID: {}).", animation_id);
        }

        // If not blocking, return immediately
        if !block {
            return Ok(post_resp);
        }

        if !silent {
            println!("Polling for results every 5 seconds...");
        }

        // Poll for results every 5 seconds until complete
        use tokio::time::{sleep, Duration};

        let results_url = format!("{}/api/animation_results/{}", base_url, animation_id);
        let animation_results: Value;
        let mut elapsed: u32 = 0;
        loop {
            let resp: Value = client
                .get(&results_url)
                .header("Authorization", format!("Bearer {}", api_key))
                .send()
                .await?
                .error_for_status()?
                .json()
                .await?;

            // Assume response is array; take first item
            let status_complete = if resp.is_array() {
                resp.get(0)
                    .and_then(|item| item.get("status"))
                    .and_then(|s| s.as_i64())
            } else {
                resp.get("status")
                    .and_then(|s| s.as_i64())
            };

            if let Some(status) = status_complete {
                match status {
                    2 => {
                        // completed successfully
                        animation_results = resp;
                        break;
                    }
                    3 => {
                        // failed and refunded
                        return Err("animation failed and refunded (status=3)".into());
                    }
                    _ => {} // 1 = generating; continue polling
                }
            }

            sleep(Duration::from_secs(5)).await;
            elapsed += 5;
            if !silent && elapsed % 30 == 0 {
                println!("Still polling ({} total seconds elapsed)", elapsed);
            }
        }

        // Determine result ID to download
        let result_id = if animation_results.is_array() {
            animation_results
                .get(0)
                .and_then(|item| item.get("id"))
                .and_then(|v| v.as_i64())
        } else {
            animation_results.get("id").and_then(|v| v.as_i64())
        }
        .ok_or("result id missing")?;

        // Download ZIP
        if !silent {
            println!("Render complete, downloading ZIP...");
        }
        let zip_url = format!("{}/api/animation_result_zip/{}", base_url, result_id);

        let mut waited_sec = 0u32;
        let bytes;
        loop {
            let resp_result = client
                .get(&zip_url)
                .header("Authorization", format!("Bearer {}", api_key))
                .send()
                .await;

            match resp_result {
                Ok(resp) => {
                    if resp.status().is_success() {
                        bytes = resp.bytes().await?;
                        break;
                    } else if resp.status().as_u16() == 500 {
                        // zip not ready yet
                        if waited_sec == 0 && !silent {
                            println!("Animation rendered successfully, waiting on .zip file...");
                        }
                    } else {
                        return Err(format!("failed to download zip: HTTP {}", resp.status()).into());
                    }
                }
                Err(err) => {
                    return Err(format!("failed to download zip: {}", err).into());
                }
            }

            if waited_sec >= 120 {
                return Err("timed out waiting for .zip file".into());
            }
            sleep(Duration::from_secs(5)).await;
            waited_sec += 5;
        }

        // Determine output file path
        let path = output_file
            .map(|s| s.to_string())
            .unwrap_or_else(|| format!("animation_{}_{}.zip", animation_id, result_id));

        tokio::fs::write(&path, &bytes).await?;

        if !silent {
            println!("ZIP saved to {}", path);
        }

        let out_json = serde_json::json!({
            "animation_id": animation_id,
            "result_id": result_id,
            "zip_path": path,
        });

        Ok(out_json)
    }

    #[allow(unused_variables)]
    pub async fn crop(input: &str, output: Option<&str>) {
        unimplemented!("crop animation");
    }

    /// Regenerate an animation using the same parameters as an existing one.
    ///
    /// Hits `POST /api/animation/regenerate/<animation_id>` and returns the JSON
    /// response (shape: `{ "animation_id": <new_id> }`).
    pub async fn regenerate(
        api_key: &str,
        base_url: &str,
        animation_id: &str,
    ) -> Result<Value, Box<dyn std::error::Error + Send + Sync>> {
        let client = reqwest::Client::new();
        let url = format!("{}/api/animation/regenerate/{}", base_url, animation_id);

        let json: Value = client
            .post(&url)
            .header("Authorization", format!("Bearer {}", api_key))
            .send()
            .await?
            .error_for_status()? // surface non-2xx responses
            .json()
            .await?;

        Ok(json)
    }

    /// Fetch a list of available animation models with their details (cost, supported durations, etc.).
    pub async fn models(
        api_key: &str,
        base_url: &str,
    ) -> Result<Value, Box<dyn std::error::Error + Send + Sync>> {
        let client = reqwest::Client::new();

        let url = format!("{}/api/animation/models", base_url);
        let models: Value = client
            .get(&url)
            .header("Authorization", format!("Bearer {}", api_key))
            .send()
            .await?
            .error_for_status()?
            .json()
            .await?;

        Ok(models)
    }
} 