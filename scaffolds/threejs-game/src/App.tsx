import { Scene, Ground, Box, Sphere, HUD } from "./components"

/** Demo scene — replace this with your game.
 *  Scene gives you: camera, lighting, physics, orbit controls.
 *  Just add objects as children. They have physics automatically. */
export default function App() {
  return (
    <>
      <HUD>
        <span>SCORE: 0</span>
        <span>HEALTH: 100</span>
      </HUD>
      <Scene bgColor="#0a0a1a" debug={false}>
        <Ground />
        <Box position={[0, 5, 0]} color="#ff6644" />
        <Box position={[1.5, 8, 0.5]} color="#44ff66" />
        <Box position={[-1, 11, -0.5]} color="#6644ff" />
        <Sphere position={[0, 15, 0]} color="#ff44aa" />
        <Sphere position={[2, 18, 1]} color="#44aaff" radius={0.7} />
      </Scene>
    </>
  )
}
