import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { contractApi } from '../../api/contracts.js';
import DataTable from '../../components/DataTable.jsx';
import DetailList from '../../components/DetailList.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import { ScorePill, StatusTag } from '../../components/Tags.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { formatDate, formatMoney } from '../../utils/format.js';
import SettlementCreateModal from '../settlements/SettlementCreateModal.jsx';
import ContractFormModal from './ContractFormModal.jsx';

const TABS = [
  { key: 'profile', label: '合同档案' },
  { key: 'restrooms', label: '服务公厕' },
  { key: 'settlements', label: '月度费用台账' },
];

export default function ContractDetailPage() {
  const { contractId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [tab, setTab] = useState('settlements');
  const [showForm, setShowForm] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  const { data: contract, loading, error, reload } = useAsync(
    () => contractApi.detail(contractId),
    [contractId],
  );

  const remove = async () => {
    if (!window.confirm('确认删除该合同？已有月度结算的合同不能删除。')) return;
    try {
      await contractApi.remove(contractId);
      toast.success('合同已删除');
      navigate('/contracts');
    } catch (err) {
      toast.error(err.message);
    }
  };

  const terminate = async () => {
    if (!window.confirm('确认提前终止该合同？终止后不再纳入新的考核结算，且需联系管理员恢复。')) return;
    try {
      await contractApi.update(contractId, { status: '已终止' });
      toast.success('合同已终止');
      reload();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <>
      <PageHeader
        title={contract ? `${contract.name}（${contract.code}）` : '合同详情'}
        description={contract ? `${contract.vendor?.name ?? ''} · ${contract.scope_text}` : '加载中…'}
        actions={
          <>
            <Link className="btn" to="/contracts">
              返回列表
            </Link>
            <button type="button" className="btn" onClick={() => setShowForm(true)}>
              编辑合同
            </button>
            {contract.effective_status === '履行中' ? (
              <button type="button" className="btn" onClick={terminate}>
                提前终止
              </button>
            ) : null}
            <button type="button" className="btn btn-danger" onClick={remove}>
              删除
            </button>
          </>
        }
      />
      <div className="content">
        {error ? <div className="alert alert-error">{error.message}</div> : null}
        {loading && !contract ? <div className="loading-block">加载中…</div> : null}

        {contract ? (
          <>
            <div className="stat-grid">
              <div className="stat-card">
                <div className="label">月度费用</div>
                <div className="value" style={{ fontSize: 26 }}>
                  ¥{formatMoney(contract.monthly_fee)}
                </div>
                <div className="foot">合同约定，考核扣款前</div>
              </div>
              <div className="stat-card is-warning">
                <div className="label">累计考核扣款</div>
                <div className="value" style={{ fontSize: 26 }}>
                  ¥{formatMoney(contract.total_deduction)}
                </div>
                <div className="foot">共 {contract.settlement_count} 个月结算记录</div>
              </div>
              <div className="stat-card is-info">
                <div className="label">累计已结算金额</div>
                <div className="value" style={{ fontSize: 26 }}>
                  ¥{formatMoney(contract.total_payable)}
                </div>
                <div className="foot">
                  考核均分 {contract.avg_score != null ? contract.avg_score.toFixed(1) : '-'}
                </div>
              </div>
            </div>

            <div className="inline">
              {TABS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`btn btn-sm${tab === item.key ? ' btn-primary' : ''}`}
                  onClick={() => setTab(item.key)}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {tab === 'profile' ? (
              <section className="card">
                <DetailList
                  items={[
                    { label: '合同编号', value: contract.code },
                    { label: '合同名称', value: contract.name },
                    {
                      label: '承包单位',
                      value: contract.vendor?.name ?? '-',
                    },
                    { label: '服务范围方式', value: contract.scope_type },
                    {
                      label: '服务范围',
                      value:
                        contract.scope_type === '按区域'
                          ? (contract.scope_districts || []).join('、')
                          : `指定 ${contract.scope_restroom_count} 座公厕`,
                    },
                    {
                      label: '合同期限',
                      value: `${formatDate(contract.start_date)} ~ ${formatDate(contract.end_date)}`,
                    },
                    { label: '月度服务费用', value: `¥${formatMoney(contract.monthly_fee)}` },
                    { label: '结算与付款约定', value: contract.payment_terms || '无' },
                    { label: '签订日期', value: formatDate(contract.signed_at) },
                    { label: '履行状态', value: <StatusTag status={contract.effective_status} /> },
                    { label: '备注', value: contract.remark || '无' },
                  ]}
                />
              </section>
            ) : null}

            {tab === 'restrooms' ? (
              <section className="card">
                <div className="card-title">
                  <h3>服务范围内公厕（{contract.restrooms.length} 座）</h3>
                  <Link className="hint" to="/restrooms">
                    公厕台账 →
                  </Link>
                </div>
                <DataTable
                  rows={contract.restrooms}
                  emptyText="服务范围内暂无公厕"
                  columns={[
                    { key: 'code', title: '公厕编号' },
                    {
                      key: 'name',
                      title: '公厕名称',
                      render: (row) => <Link to={`/restrooms/${row.id}`}>{row.name}</Link>,
                    },
                    { key: 'district', title: '区域' },
                    { key: 'manager', title: '保洁责任人' },
                    { key: 'status', title: '状态', render: (row) => <StatusTag status={row.status} /> },
                  ]}
                />
              </section>
            ) : null}

            {tab === 'settlements' ? (
              <section className="card">
                <div className="card-title">
                  <h3>月度费用结算与考核台账</h3>
                  <button
                    type="button"
                    className="btn btn-sm btn-primary"
                    onClick={() => setShowCreate(true)}
                  >
                    + 登记月度结算
                  </button>
                </div>
                <DataTable
                  rows={contract.settlements}
                  emptyText="暂无月度结算记录，点击右上角登记"
                  columns={[
                    { key: 'code', title: '结算单号' },
                    { key: 'period_month', title: '考核月份' },
                    {
                      key: 'monthly_fee',
                      title: '月度费用',
                      render: (row) => `¥${formatMoney(row.monthly_fee)}`,
                    },
                    {
                      key: 'avg_score',
                      title: '考核均分',
                      render: (row) =>
                        row.avg_score != null ? <ScorePill score={row.avg_score} /> : '-',
                    },
                    { key: 'issue_count', title: '新增问题' },
                    { key: 'overdue_count', title: '超期未闭环' },
                    {
                      key: 'total_deduction',
                      title: '扣款合计',
                      render: (row) => (
                        <span className={row.total_deduction > 0 ? 'money-negative' : ''}>
                          ¥{formatMoney(row.total_deduction)}
                        </span>
                      ),
                    },
                    {
                      key: 'payable_amount',
                      title: '应结算金额',
                      render: (row) =>
                        row.status === '待考核' ? (
                          <span className="muted">待考核</span>
                        ) : (
                          <strong>¥{formatMoney(row.payable_amount)}</strong>
                        ),
                    },
                    { key: 'status', title: '状态', render: (row) => <StatusTag status={row.status} /> },
                    {
                      key: 'actions',
                      title: '操作',
                      render: (row) => (
                        <Link className="btn-link" to={`/settlements/${row.id}`}>
                          结算详情
                        </Link>
                      ),
                    },
                  ]}
                />
              </section>
            ) : null}
          </>
        ) : null}
      </div>

      {showForm && contract ? (
        <ContractFormModal contract={contract} onClose={() => setShowForm(false)} onSaved={reload} />
      ) : null}
      {showCreate && contract ? (
        <SettlementCreateModal
          contract={contract}
          onClose={() => setShowCreate(false)}
          onCreated={(settlementId) => navigate(`/settlements/${settlementId}`)}
        />
      ) : null}
    </>
  );
}
