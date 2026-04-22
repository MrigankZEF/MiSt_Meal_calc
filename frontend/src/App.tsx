import { BrowserRouter, Route, Routes } from 'react-router-dom';
import Nav from './components/Nav';
import { AuthProvider } from './context/AuthContext';
import History from './routes/History';
import Landing from './routes/Landing';
import Login from './routes/Login';
import MealMode from './routes/MealMode';
import ProcurementMode from './routes/ProcurementMode';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Nav />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/meal" element={<MealMode />} />
          <Route path="/procurement" element={<ProcurementMode />} />
          <Route path="/history" element={<History />} />
          <Route path="/login" element={<Login />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
