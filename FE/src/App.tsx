import { Route, Routes } from 'react-router'
import Camera from './app/Camera'
import Home from './app/Home'

function App() {
  return (
    <div>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/camera" element={<Camera />} />
      </Routes>
    </div>
  )
}

export default App
