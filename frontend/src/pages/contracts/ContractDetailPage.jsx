import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { contractApi } from '../../api/contracts.js';
import { settlementApi } from '../../api/settlements.js';
import DataTable from '../../components/DataTable.jsx';
import DetailList from '../../components/DetailList.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import { ScorePill, StatusTag } from '../../components/Tags.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { formatDate, formatMoney } from '../../utils/format.js';
import ContractFormModal from './ContractFormModal.jsx';
import SettlementCreateModal from '../settlements/SettlementCreateModal.jsx';
import SettlementDetailModal from '../settlements/SettlementDetailModal.jsx';

function AssessGradeTag({ grade }) {
  const tone =
    grade === '优秀'
      ? 'tag-success'
      : grade === '合格'
        ? 'tag-primary'
        : grade === '基本合格'
          ? 'tag-warning'
          : grade === '不合格'
            ? 'tag-danger'
            : 'tag-neutral';
  return <span className={`tag ${tone}`}>{grade || '未考核'}</span>;
}

export default function ContractDetailPage() {
  const { contractId } = useParams();
  const [showEdit, setShowEdit] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [activeSettlement, setActiveSettlement] = useState(null);

  const { data: contract, loading, error, reload } = useAsync(
    () => contractApi.detail(contractId),
    [contractId],
  );

  // 该合同的结算记录
  const { data: rowsData, reload: reloadSettlements } = useAsync(
    () => settlementApi.list({ contract_id: contractId, page: 1, page_size: 100 }),
    [contractId],
  );

  const terminate = () => {
    const reason = window.prompt('确认提前终止该合同？请填写终止原因：');
    if (reason === null) return;
    if (!reason.trim()) return;
    contractApi
      .terminate(contractId, { reason: reason.trim() })
      .then(() => {
        reload();
      })
      .catch((err) => window.alert(err.message));
  };

  const rows = rowsData?.items || [];

  return (
    <>
      <PageHeader
        title={contract ? contract.name : '合同详情'}
        description={contract ? `${contract.code} · ${contract.vendor?.name ?? ''}` : '加载中…'}
        actions={
          <>
            <Link className="btn" to="/contracts">
              返回合同列表
            </Link>
            <button type="button" className="btn" onClick={() => setShowEdit(true)}>
              编辑合同
            </button>
            {contract?.status === '履约中' ? (
              <button type="button" className="btn btn-danger" onClick={terminate}>
                终止合同
              </button>
            ) : null}
            {contract?.status === '履约中' ? (
              <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
                + 生成月度结算单
              </button>
            ) : null}
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
                <div className="label">月度服务费</div>
                <div className="value">
                  {formatMoney(contract.monthly_fee)}
                  <span className="unit">元/月</span>
                </div>
                <div className="foot">合同期内按月考核结算</div>
              </div>
              <div className="stat-card is-info">
                <div className="label">服务公厕</div>
                <div className="value">
                  {contract.restroom_count}
                  <span className="unit">座</span>
                </div>
                <div className="foot">{(contract.scope_districts || []).join('、') || '未划定区域'}</div>
              </div>
              <div className="stat-card">
                <div className="label">已结算月份</div>
                <div className="value">
                  {contract.settled_count}
                  <span className="unit">个月</span>
                </div>
                <div className="foot">累计已付 ¥ {formatMoney(contract.settled_total)}</div>
              </div>
              <div className={`stat-card${contract.status === '履约中' ? ' is-info' : ''}`}>
                <div className="label">合同状态</div>
                <div className="value" style={{ fontSize: 26 }}>
                  <StatusTag status={contract.status} />
                </div>
                <div className="foot">
                  {formatDate(contract.start_date)} ~ {formatDate(contract.end_date)}
                </div>
              </div>
            </div>

            <section className="card">
              <div className="card-title">
                <h3>合同信息</h3>
              </div>
              <DetailList
                items={[
                  { label: '承包单位', value: contract.vendor?.name ?? '-' },
                  {
                    label: '单位联系人',
                    value: contract.vendor
                      ? `${contract.vendor.contact_person || '-'} ${contract.vendor.contact_phone || ''}`
                      : '-',
                  },
                  { label: '服务范围', value: contract.service_scope || '-' },
                  { label: '服务区域', value: (contract.scope_districts || []).join('、') || '-' },
                  { label: '合同期限', value: `${formatDate(contract.start_date)} ~ ${formatDate(contract.end_date)}` },
                  { label: '签订日期', value: formatDate(contract.signed_date) },
                  { label: '付款约定', value: contract.payment_terms || '-' },
                  { label: '备注', value: contract.remark || '无' },
                  ...(contract.terminate_reason
                    ? [{ label: '终止原因', value: contract.terminate_reason }]
                    : []),
                ]}
              />
            </section>

            <section className="card">
              <div className="card-title">
                <h3>服务范围公厕</h3>
                <span className="hint">共 {contract.restrooms?.length || 0} 座</span>
              </div>
              <DataTable
                rows={contract.restrooms || []}
                emptyText="合同尚未划定服务公厕"
                columns={[
                  { key: 'code', title: '编号' },
                  {
                    key: 'name',
                    title: '公厕名称',
                    render: (row) => <Link to={`/restrooms/${row.id}`}>{row.name}</Link>,
                  },
                  { key: 'district', title: '区域' },
                  { key: 'address', title: '地址', wrap: true },
                ]}
              />
            </section>

            <section className="card">
              <div className="card-title">
                <h3>月度费用与考核台账</h3>
                <span className="hint">点击月份查看扣款依据，可追溯到巡查与问题记录</span>
              </div>
              <DataTable
                rows={rows}
                emptyText="暂无月度结算单，点击右上角生成"
                columns={[
                  { key: 'code', title: '结算单号' },
                  { key: 'period', title: '考核月份' },
                  {
                    key: 'inspection_count',
                    title: '巡查',
                    render: (row) => `${row.inspection_count} 次`,
                  },
                  {
                    key: 'avg_score',
                    title: '月均分',
                    render: (row) =>
                      row.avg_score == null ? (
                        <span className="muted">无</span>
                      ) : (
                        <ScorePill score={row.avg_score} />
                      ),
                  },
                  {
                    key: 'issues',
                    title: '新问题 / 超期 / 驳回',
                    render: (row) =>
                      `${row.issue_new_count} / ${row.issue_overdue_count} / ${row.issue_reject_count}`,
                  },
                  {
                    key: 'monthly_fee',
                    title: '月费用',
                    render: (row) => formatMoney(row.monthly_fee),
                  },
                  {
                    key: 'total_deduction',
                    title: '扣款合计',
                    render: (row) => (
                      <span className={row.total_deduction > 0 ? 'money-deduct' : ''}>
                        {row.total_deduction > 0 ? '-' : ''}
                        {formatMoney(row.total_deduction)}
                      </span>
                    ),
                  },
                  {
                    key: 'payable_amount',
                    title: '应付金额',
                    render: (row) => <strong>¥ {formatMoney(row.payable_amount)}</strong>,
                  },
                  {
                    key: 'assess_grade',
                    title: '考核等级',
                    render: (row) => <AssessGradeTag grade={row.assess_grade} />,
                  },
                  { key: 'status', title: '状态', render: (row) => <StatusTag status={row.status} /> },
                  {
                    key: 'actions',
                    title: '操作',
                    render: (row) => (
                      <button type="button" className="btn-link" onClick={() => setActiveSettlement(row.id)}>
                        详情 / 结算
                      </button>
                    ),
                  },
                ]}
              />
            </section>
          </>
        ) : null}
      </div>

      {showEdit && contract ? (
        <ContractFormModal contract={contract} onClose={() => setShowEdit(false)} onSaved={reload} />
      ) : null}
      {showCreate && contract ? (
        <SettlementCreateModal
          contract={contract}
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            reload();
            reloadSettlements();
          }}
        />
      ) : null}
      {activeSettlement ? (
        <SettlementDetailModal
          settlementId={activeSettlement}
          onClose={() => setActiveSettlement(null)}
          onChanged={() => {
            reload();
            reloadSettlements();
          }}
        />
      ) : null}
    </>
  );
}
