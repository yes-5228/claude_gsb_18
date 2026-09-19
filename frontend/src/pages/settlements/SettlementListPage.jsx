import { useState } from 'react';
import { Link } from 'react-router-dom';

import { settlementApi } from '../../api/settlements.js';
import { vendorApi } from '../../api/vendors.js';
import DataTable from '../../components/DataTable.jsx';
import Field from '../../components/Field.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Pagination from '../../components/Pagination.jsx';
import { StatusTag } from '../../components/Tags.jsx';
import { useDictionaries } from '../../hooks/useDictionaries.js';
import { useListQuery } from '../../hooks/useListQuery.js';
import { useAsync } from '../../hooks/useAsync.js';
import { formatMoney } from '../../utils/format.js';
import SettlementDetailModal from './SettlementDetailModal.jsx';

const NOW = new Date();
const DEFAULT_FILTERS = {
  keyword: '',
  vendor_id: '',
  status: '',
  period_year: String(NOW.getFullYear()),
  period_month: '',
};

function GradeTag({ grade }) {
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

export default function SettlementListPage() {
  const { dictionaries } = useDictionaries();
  const [activeId, setActiveId] = useState(null);
  const { data: vendors } = useAsync(() => vendorApi.options(), []);

  const list = useListQuery((params) => settlementApi.list(params), DEFAULT_FILTERS, 15);

  const monthOptions = Array.from({ length: 12 }, (_, index) => index + 1);
  const yearOptions = [NOW.getFullYear() - 1, NOW.getFullYear(), NOW.getFullYear() + 1];

  const totals = list.items.reduce(
    (acc, row) => {
      acc.fee += row.monthly_fee;
      acc.deduction += row.total_deduction;
      acc.payable += row.payable_amount;
      return acc;
    },
    { fee: 0, deduction: 0, payable: 0 },
  );

  return (
    <>
      <PageHeader
        title="费用台账"
        description="全部外包合同的月度考核扣款与结算金额，金额与考核结果可互相追溯"
      />
      <div className="content">
        <section className="card">
          <div className="filter-bar">
            <Field label="关键字" full>
              <input
                value={list.filters.keyword}
                placeholder="结算单号 / 合同名称 / 合同编号"
                onChange={(event) => list.updateFilter('keyword', event.target.value)}
              />
            </Field>
            <Field label="承包单位">
              <select
                value={list.filters.vendor_id}
                onChange={(event) => list.updateFilter('vendor_id', event.target.value)}
              >
                <option value="">全部</option>
                {(vendors || []).map((vendor) => (
                  <option key={vendor.id} value={vendor.id}>
                    {vendor.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="考核年份">
              <select
                value={list.filters.period_year}
                onChange={(event) => list.updateFilter('period_year', event.target.value)}
              >
                <option value="">全部年份</option>
                {yearOptions.map((year) => (
                  <option key={year} value={year}>
                    {year} 年
                  </option>
                ))}
              </select>
            </Field>
            <Field label="考核月份">
              <select
                value={list.filters.period_month}
                onChange={(event) => list.updateFilter('period_month', event.target.value)}
              >
                <option value="">全年</option>
                {monthOptions.map((month) => (
                  <option key={month} value={month}>
                    {month} 月
                  </option>
                ))}
              </select>
            </Field>
            <Field label="结算状态">
              <select
                value={list.filters.status}
                onChange={(event) => list.updateFilter('status', event.target.value)}
              >
                <option value="">全部</option>
                {(dictionaries?.settlement_status || ['已考核', '已结算']).map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </Field>
            <button type="button" className="btn" onClick={list.resetFilters}>
              重置
            </button>
          </div>
        </section>

        <div className="stat-grid">
          <div className="stat-card">
            <div className="label">本页月费用合计</div>
            <div className="value">
              {formatMoney(totals.fee)}
              <span className="unit">元</span>
            </div>
          </div>
          <div className="stat-card is-warning">
            <div className="label">本页扣款合计</div>
            <div className="value">
              {formatMoney(totals.deduction)}
              <span className="unit">元</span>
            </div>
          </div>
          <div className="stat-card is-info">
            <div className="label">本页应付合计</div>
            <div className="value">
              {formatMoney(totals.payable)}
              <span className="unit">元</span>
            </div>
          </div>
        </div>

        <section className="card">
          <DataTable
            loading={list.loading}
            error={list.error}
            rows={list.items}
            emptyText="暂无结算记录，请先在合同详情中生成月度结算单"
            columns={[
              { key: 'code', title: '结算单号' },
              { key: 'period', title: '考核月份' },
              {
                key: 'contract',
                title: '合同',
                wrap: true,
                render: (row) =>
                  row.contract ? (
                    <Link to={`/contracts/${row.contract.id}`}>{row.contract.name}</Link>
                  ) : (
                    `合同 #${row.contract_id}`
                  ),
              },
              {
                key: 'quality',
                title: '巡查次数 / 均分',
                render: (row) =>
                  `${row.inspection_count} 次 / ${row.avg_score == null ? '无' : row.avg_score}`,
              },
              {
                key: 'issues',
                title: '新/超期/驳回',
                render: (row) =>
                  `${row.issue_new_count}/${row.issue_overdue_count}/${row.issue_reject_count}`,
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
                    -{formatMoney(row.total_deduction)}
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
                render: (row) => <GradeTag grade={row.assess_grade} />,
              },
              { key: 'status', title: '状态', render: (row) => <StatusTag status={row.status} /> },
              {
                key: 'actions',
                title: '操作',
                render: (row) => (
                  <button type="button" className="btn-link" onClick={() => setActiveId(row.id)}>
                    扣款追溯
                  </button>
                ),
              },
            ]}
          />
          <Pagination meta={list.meta} onPageChange={list.setPage} />
        </section>
      </div>

      {activeId ? (
        <SettlementDetailModal
          settlementId={activeId}
          onClose={() => setActiveId(null)}
          onChanged={list.reload}
        />
      ) : null}
    </>
  );
}
