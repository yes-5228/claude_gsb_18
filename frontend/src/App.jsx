import { Navigate, Route, Routes } from 'react-router-dom';

import Layout from './components/Layout.jsx';
import DashboardPage from './pages/dashboard/DashboardPage.jsx';
import ContractDetailPage from './pages/contracts/ContractDetailPage.jsx';
import ContractListPage from './pages/contracts/ContractListPage.jsx';
import InspectionListPage from './pages/inspections/InspectionListPage.jsx';
import IssueDetailPage from './pages/issues/IssueDetailPage.jsx';
import IssueListPage from './pages/issues/IssueListPage.jsx';
import RestroomDetailPage from './pages/restrooms/RestroomDetailPage.jsx';
import RestroomListPage from './pages/restrooms/RestroomListPage.jsx';
import SettlementDetailPage from './pages/settlements/SettlementDetailPage.jsx';
import SettlementListPage from './pages/settlements/SettlementListPage.jsx';
import VendorListPage from './pages/vendors/VendorListPage.jsx';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/restrooms" element={<RestroomListPage />} />
        <Route path="/restrooms/:restroomId" element={<RestroomDetailPage />} />
        <Route path="/inspections" element={<InspectionListPage />} />
        <Route path="/issues" element={<IssueListPage />} />
        <Route path="/issues/:issueId" element={<IssueDetailPage />} />
        <Route path="/vendors" element={<VendorListPage />} />
        <Route path="/contracts" element={<ContractListPage />} />
        <Route path="/contracts/:contractId" element={<ContractDetailPage />} />
        <Route path="/settlements" element={<SettlementListPage />} />
        <Route path="/settlements/:settlementId" element={<SettlementDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
