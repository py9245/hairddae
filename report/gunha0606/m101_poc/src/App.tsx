import { BrowserRouter, Routes, Route } from "react-router-dom";
import Bald from "./app/Bald";
import Home from "./app/Home";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/bald" element={<Bald />} />
      </Routes>
    </BrowserRouter>
  );
}