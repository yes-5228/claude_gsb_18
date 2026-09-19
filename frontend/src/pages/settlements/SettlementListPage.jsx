import { useState } from 'react';
import { Link } from 'react-router-dom';

import { contractApi } from '../../api/contracts.js';
import { settlementApi } from '../../api/settlements.js';
import { vendorApi } from '../../api/vendors.js';
import DataTable from '../../components/DataTable.jsx';
import Field from '../../components/Field.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Pagination from '../../components/Pagination.jsx';
import { ScorePill, StatusTag } from '../../components/Tags.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useDictionaries } from '../../hooks/useDictionaries.js';
import { useListQuery } from '../../hooks/useListQuery.js';
import { currentMonth, formatMoney } from '../../utils/format.js';

const DEFAULT_FILTERS = {
  keyword: '',
  status: '',
  period_month: currentMonth(),
  vendor_id: '',
  contract_id: '',
};

export default function SettlementListPage() {
  const { dictionaries } = useDictionaries();
  const toast = useToast();
  const [showAllMonths, setShowAllMonths] = useState(false);

  const list = useListQuery((params) => settlementApi.list(params), DEFAULT_FILTERS, 15);
  const { data: vendors } = useAsync(() => vendorApi.options({ page_size: 100 }), []);
  const { data: contractPage } = useAsync(
    () =>
      contractApi.list({
        vendor_id: list.filters.vendor_id || undefined,
        page_size: 100,
      }),
    [list.filters.vendor_id],
  );

  const remove = async (row) => {
    if (!window.confirm(`确认删除结算单 ${row.code}？已结算的台账需先撤销结算。`)) return;
    try {
      await settlementApi.remove(row.id);
      toast.success('删除成功');
      list.reload();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <>
      <PageHeader
        title="月度费用台账"
        description="按合同月份登记结算，结合巡查质量与问题整改情况计算考核扣款，结算金额可逐笔追溯"
      />
      <div className="content">
        <section className="card">
          <div className="filter-bar">
            <Field label="考核月份">
              <input
                type="month"
                value={showAllMonths ? '' : list.filters.period_month}
                onChange={(event) => {
                  setShowAllMonths(false);
                  list.updateFilter('period_month', event.target.value);
                }}
              />
            </Field>
            <Field label="全部月份">
              <label className="checkbox-row" style={{ paddingTop: 6 }}>
                <input
                  type="checkbox"
                  checked={showAllMonths}
                  onChange={(event) => {
                    setShowAllMonths(event.target.checked);
                    list.updateFilter('period_month', event.target.checked ? '' : currentMonth());
                  }}
                />
                不限月份
              </label>
            </Field>
            <Field label="外包单位">
              <select
                value={list.filters.vendor_id}
                onChange={(event) => {
                  list.updateFilter('vendor_id', event.target.value);
                  list.updateFilter('contract_id', '');
                }}
              >
                <option value="">全部单位</option>
                {(vendors || []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="合同">
              <select
                value={list.filters.contract_id}
                onChange={(event) => list.updateFilter('contract_id', event.target.value)}
              >
                <option value="">全部合同</option>
                {(contractPage?.items ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.code} {item.name}
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
                {(dictionaries?.settlement_status || ['待考核', '已考核', '已结算']).map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </Field>
            <Field label="关键字" full>
              <input
                value={list.filters.keyword}
                placeholder="结算单号 / 合同号 / 合同名称"
                onChange={(event) => list.updateFilter('keyword', event.target.value)}
              />
            </Field>
            <button type="button" className="btn" onClick={list.resetFilters}>
              重置
            </button>
          </div>
        </section>

        <section className="card">
          <DataTable
            loading={list.loading}
            error={list.error}
            rows={list.items}
            emptyText="暂无月度结算记录，可在合同详情中登记"
            columns={[
              { key: 'code', title: '结算单号' },
              { key: 'period_month', title: '考核月份' },
              {
                key: 'contract',
                title: '合同',
                wrap: true,
                render: (row) => (
                  <Link to={`/contracts/${row.contract_id}`}>
                    {row.contract?.name ?? row.contract_id}
                  </Link>
                ),
              },
              { key: 'vendor', title: '承包单位', render: (row) => row.vendor?.name ?? '-' },
              {
                key: 'monthly_fee',
                title: '月度费用',
                render: (row) => `¥${formatMoney(row.monthly_fee)}`,
              },
              {
                key: 'avg_score',
                title: '考核均分',
                render: (row) =>
                  row.avg_score != null ? <ScorePill score={row.avg_score} /> : (
                    <span className="muted">未考核</span>
                  ),
              },
              {
                key: 'quality',
                title: '质量扣款',
                render: (row) => `¥${formatMoney(row.quality_deduction)}`,
              },
              {
                key: 'issue_ded',
                title: '问题+超期扣款',
                render: (row) =>
                  `¥${formatMoney(row.issue_deduction + row.overdue_deduction)}`,
              },
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
                    <span className="muted">-</span>
                  ) : (
                    <strong>¥{formatMoney(row.payable_amount)}</strong>
                  ),
              },
              { key: 'status', title: '状态', render: (row) => <StatusTag status={row.status} /> },
              {
                key: 'actions',
                title: '操作',
                render: (row) => (
                  <div className="inline">
                    <Link className="btn-link" to={`/settlements/${row.id}`}>
                      详情/考核
                    </Link>
                    <button type="button" className="btn-link danger" onClick={() => remove(row)}>
                      删除
                    </button>
                  </div>
                ),
              },
            ]}
          />
          <Pagination meta={list.meta} onPageChange={list.setPage} />
        </section>
      </div>
    </>
  );
}
