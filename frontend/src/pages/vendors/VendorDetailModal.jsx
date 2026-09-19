import { Link } from 'react-router-dom';

import { contractApi } from '../../api/contracts.js';
import { vendorApi } from '../../api/vendors.js';
import DataTable from '../../components/DataTable.jsx';
import DetailList from '../../components/DetailList.jsx';
import Modal from '../../components/Modal.jsx';
import { StatusTag } from '../../components/Tags.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { formatDate, formatMoney } from '../../utils/format.js';

export default function VendorDetailModal({ vendorId, onClose }) {
  const { data: vendor } = useAsync(() => vendorApi.detail(vendorId), [vendorId]);
  const { data: contractPage } = useAsync(
    () => contractApi.list({ vendor_id: vendorId, page_size: 50 }),
    [vendorId],
  );

  return (
    <Modal
      title={vendor ? `外包单位 - ${vendor.name}` : '单位详情'}
      onClose={onClose}
      width={860}
      footer={
        <Link className="btn btn-primary" to={`/contracts?vendor_id=${vendorId}`} onClick={onClose}>
          查看该单位全部合同
        </Link>
      }
    >
      {vendor ? (
        <>
          <div className="stat-grid">
            <div className="stat-card">
              <div className="label">合同总数</div>
              <div className="value">
                {vendor.contract_count}
                <span className="unit">份</span>
              </div>
              <div className="foot">履行中 {vendor.active_contract_count} 份</div>
            </div>
            <div className="stat-card is-info">
              <div className="label">本年已结算金额</div>
              <div className="value" style={{ fontSize: 26 }}>
                ¥{formatMoney(vendor.settled_amount_year)}
              </div>
              <div className="foot">考核扣款后实付</div>
            </div>
            <div className="stat-card is-warning">
              <div className="label">本年考核扣款</div>
              <div className="value" style={{ fontSize: 26 }}>
                ¥{formatMoney(vendor.deduction_total_year)}
              </div>
              <div className="foot">质量 + 问题整改扣款</div>
            </div>
          </div>

          <div className="section-title">单位档案</div>
          <DetailList
            items={[
              { label: '单位编号', value: vendor.code },
              { label: '合作状态', value: <StatusTag status={vendor.status} /> },
              { label: '统一社会信用代码', value: vendor.license_no || '无' },
              { label: '联系人', value: vendor.contact_person || '无' },
              { label: '联系电话', value: vendor.contact_phone || '无' },
              { label: '单位地址', value: vendor.address || '无' },
              { label: '建档时间', value: formatDate(vendor.created_at) },
              { label: '备注', value: vendor.remark || '无' },
            ]}
          />

          <div className="section-title">合同清单</div>
          <DataTable
            loading={!contractPage}
            rows={contractPage?.items ?? []}
            emptyText="该单位暂无合同"
            columns={[
              { key: 'code', title: '合同编号' },
              {
                key: 'name',
                title: '合同名称',
                render: (row) => (
                  <Link to={`/contracts/${row.id}`} onClick={onClose}>
                    {row.name}
                  </Link>
                ),
              },
              {
                key: 'period',
                title: '合同期限',
                render: (row) => `${formatDate(row.start_date)} ~ ${formatDate(row.end_date)}`,
              },
              {
                key: 'monthly_fee',
                title: '月度费用',
                render: (row) => `¥${formatMoney(row.monthly_fee)}`,
              },
              {
                key: 'effective_status',
                title: '状态',
                render: (row) => <StatusTag status={row.effective_status} />,
              },
            ]}
          />
        </>
      ) : (
        <div className="loading-block">加载中…</div>
      )}
    </Modal>
  );
}
