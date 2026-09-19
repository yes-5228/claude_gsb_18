import { useState } from 'react';
import { Link } from 'react-router-dom';

import { vendorApi } from '../../api/vendors.js';
import DataTable from '../../components/DataTable.jsx';
import Field from '../../components/Field.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Pagination from '../../components/Pagination.jsx';
import { StatusTag } from '../../components/Tags.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useDictionaries } from '../../hooks/useDictionaries.js';
import { useListQuery } from '../../hooks/useListQuery.js';
import VendorDetailModal from './VendorDetailModal.jsx';
import VendorFormModal from './VendorFormModal.jsx';

const DEFAULT_FILTERS = { keyword: '', status: '' };

export default function VendorListPage() {
  const { dictionaries } = useDictionaries();
  const toast = useToast();
  const [editing, setEditing] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [active, setActive] = useState(null);

  const list = useListQuery((params) => vendorApi.list(params), DEFAULT_FILTERS, 10);

  const remove = async (row) => {
    if (!window.confirm(`确认删除外包单位「${row.name}」？`)) return;
    try {
      await vendorApi.remove(row.id);
      toast.success('删除成功');
      list.reload();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <>
      <PageHeader
        title="外包单位"
        description="登记保洁服务外包单位档案，作为合同签订与费用结算的主体"
        actions={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setEditing(null);
              setShowForm(true);
            }}
          >
            + 登记单位
          </button>
        }
      />
      <div className="content">
        <section className="card">
          <div className="filter-bar">
            <Field label="关键字" full>
              <input
                value={list.filters.keyword}
                placeholder="单位名称 / 编号 / 联系人 / 信用代码"
                onChange={(event) => list.updateFilter('keyword', event.target.value)}
              />
            </Field>
            <Field label="合作状态">
              <select
                value={list.filters.status}
                onChange={(event) => list.updateFilter('status', event.target.value)}
              >
                <option value="">全部</option>
                {(dictionaries?.vendor_status || []).map((item) => (
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
            emptyText="暂无外包单位"
            columns={[
              { key: 'code', title: '单位编号' },
              {
                key: 'name',
                title: '单位名称',
                render: (row) => (
                  <button type="button" className="btn-link" onClick={() => setActive(row)}>
                    {row.name}
                  </button>
                ),
              },
              { key: 'contact_person', title: '联系人' },
              { key: 'contact_phone', title: '联系电话' },
              { key: 'status', title: '状态', render: (row) => <StatusTag status={row.status} /> },
              {
                key: 'actions',
                title: '操作',
                render: (row) => (
                  <div className="inline">
                    <button type="button" className="btn-link" onClick={() => setActive(row)}>
                      详情
                    </button>
                    <Link className="btn-link" to={`/contracts?vendor_id=${row.id}`}>
                      合同台账
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
        <VendorFormModal
          vendor={editing}
          onClose={() => setShowForm(false)}
          onSaved={list.reload}
        />
      ) : null}
      {active ? <VendorDetailModal vendorId={active.id} onClose={() => setActive(null)} /> : null}
    </>
  );
}
