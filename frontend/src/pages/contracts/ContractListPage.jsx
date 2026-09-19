import { useState } from 'react';
import { Link } from 'react-router-dom';

import { contractApi } from '../../api/contracts.js';
import { restroomApi } from '../../api/restrooms.js';
import { vendorApi } from '../../api/vendors.js';
import DataTable from '../../components/DataTable.jsx';
import Field from '../../components/Field.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Pagination from '../../components/Pagination.jsx';
import { StatusTag } from '../../components/Tags.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useDictionaries } from '../../hooks/useDictionaries.js';
import { useListQuery } from '../../hooks/useListQuery.js';
import { formatDate, formatMoney } from '../../utils/format.js';
import ContractFormModal from './ContractFormModal.jsx';

const DEFAULT_FILTERS = { keyword: '', vendor_id: '', status: '', district: '' };

export default function ContractListPage() {
  const { dictionaries } = useDictionaries();
  const toast = useToast();
  const [editing, setEditing] = useState(null);
  const [showForm, setShowForm] = useState(false);

  const list = useListQuery((params) => contractApi.list(params), DEFAULT_FILTERS, 10);
  const { data: vendors } = useAsync(() => vendorApi.options(), []);
  const { data: districts } = useAsync(() => restroomApi.districts(), []);

  const remove = async (row) => {
    if (!window.confirm(`确认删除合同「${row.name}」？已有结算记录时将被拒绝。`)) return;
    try {
      await contractApi.remove(row.id);
      toast.success('合同已删除');
      list.reload();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const terminate = async (row) => {
    const reason = window.prompt(`确认提前终止合同「${row.name}」？\n请填写终止原因：`);
    if (reason === null) return;
    if (!reason.trim()) {
      toast.error('终止原因不能为空');
      return;
    }
    try {
      await contractApi.terminate(row.id, { reason: reason.trim() });
      toast.success('合同已终止');
      list.reload();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <>
      <PageHeader
        title="外包合同"
        description="登记承包单位、服务范围、合同期限与月度服务费"
        actions={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setEditing(null);
              setShowForm(true);
            }}
          >
            + 登记合同
          </button>
        }
      />
      <div className="content">
        <section className="card">
          <div className="filter-bar">
            <Field label="关键字" full>
              <input
                value={list.filters.keyword}
                placeholder="合同名称 / 编号 / 服务范围"
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
            <Field label="合同状态">
              <select
                value={list.filters.status}
                onChange={(event) => list.updateFilter('status', event.target.value)}
              >
                <option value="">全部</option>
                {(dictionaries?.contract_status || ['履约中', '已终止', '已到期']).map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </Field>
            <Field label="服务区域">
              <select
                value={list.filters.district}
                onChange={(event) => list.updateFilter('district', event.target.value)}
              >
                <option value="">全部</option>
                {(districts || []).map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
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
            emptyText="暂无外包合同"
            columns={[
              { key: 'code', title: '合同编号' },
              {
                key: 'name',
                title: '合同名称',
                wrap: true,
                render: (row) => <Link to={`/contracts/${row.id}`}>{row.name}</Link>,
              },
              {
                key: 'vendor',
                title: '承包单位',
                render: (row) => row.vendor?.name ?? '-',
              },
              {
                key: 'period',
                title: '合同期限',
                render: (row) => `${formatDate(row.start_date)} ~ ${formatDate(row.end_date)}`,
              },
              {
                key: 'monthly_fee',
                title: '月费用',
                render: (row) => `¥ ${formatMoney(row.monthly_fee)}`,
              },
              {
                key: 'restrooms',
                title: '服务公厕',
                render: (row) => `${row.restrooms?.length || 0} 座`,
              },
              { key: 'status', title: '状态', render: (row) => <StatusTag status={row.status} /> },
              {
                key: 'actions',
                title: '操作',
                render: (row) => (
                  <div className="inline">
                    <Link className="btn-link" to={`/contracts/${row.id}`}>
                      费用台账
                    </Link>
                    <button
                      type="button"
                      className="btn-link"
                      onClick={() => {
                        setEditing(row);
                        setShowForm(true);
                      }}
                    >
                      编辑
                    </button>
                    {row.status === '履约中' ? (
                      <button type="button" className="btn-link danger" onClick={() => terminate(row)}>
                        终止
                      </button>
                    ) : null}
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

      {showForm ? (
        <ContractFormModal
          contract={editing}
          onClose={() => setShowForm(false)}
          onSaved={list.reload}
        />
      ) : null}
    </>
  );
}
