import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { contractApi } from '../../api/contracts.js';
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

const DEFAULT_FILTERS = { keyword: '', status: '', scope_type: '', vendor_id: '' };

export default function ContractListPage() {
  const { dictionaries } = useDictionaries();
  const toast = useToast();
  const [searchParams] = useSearchParams();
  const [editing, setEditing] = useState(null);
  const [showForm, setShowForm] = useState(false);

  const initialVendor = searchParams.get('vendor_id') || '';
  const list = useListQuery(
    (params) => contractApi.list(params),
    { ...DEFAULT_FILTERS, vendor_id: initialVendor },
    10,
  );
  const { data: vendors } = useAsync(() => vendorApi.options({ page_size: 100 }), []);

  const remove = async (row) => {
    if (!window.confirm(`确认删除合同「${row.name}」？已有月度结算的合同不能删除。`)) return;
    try {
      await contractApi.remove(row.id);
      toast.success('删除成功');
      list.reload();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <>
      <PageHeader
        title="外包合同"
        description="登记外包单位、服务范围、合同期限与月度费用，月度考核结算以合同为依据"
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
                placeholder="合同名称 / 合同编号"
                onChange={(event) => list.updateFilter('keyword', event.target.value)}
              />
            </Field>
            <Field label="承包单位">
              <select
                value={list.filters.vendor_id}
                onChange={(event) => list.updateFilter('vendor_id', event.target.value)}
              >
                <option value="">全部单位</option>
                {(vendors || []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="履行状态">
              <select
                value={list.filters.status}
                onChange={(event) => list.updateFilter('status', event.target.value)}
              >
                <option value="">全部</option>
                {(dictionaries?.contract_status || []).map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </Field>
            <Field label="服务范围">
              <select
                value={list.filters.scope_type}
                onChange={(event) => list.updateFilter('scope_type', event.target.value)}
              >
                <option value="">全部</option>
                <option value="按区域">按区域</option>
                <option value="指定公厕">指定公厕</option>
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
              { key: 'scope_text', title: '服务范围' },
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
              {
                key: 'actions',
                title: '操作',
                render: (row) => (
                  <div className="inline">
                    <Link className="btn-link" to={`/contracts/${row.id}`}>
                      台账详情
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
          presetVendorId={!editing ? initialVendor : null}
          onClose={() => setShowForm(false)}
          onSaved={list.reload}
        />
      ) : null}
    </>
  );
}
