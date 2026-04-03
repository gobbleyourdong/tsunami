// TODO: Replace with your 3D game
// Scene gives you: camera, lighting, physics, orbit controls.
// Just add objects as children.
import { Scene, Ground, Box } from "./components"

export default function App() {
  return (
    <Scene>
      <Ground />
      <Box position={[0, 3, 0]} />
    </Scene>
  )
}
