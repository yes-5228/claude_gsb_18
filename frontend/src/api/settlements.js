import { http } from './client.js';

const RESOURCE = '/settlements';

export const settlementApi = {
  list: (params) => http.get(RESOURCE, params),
  detail: (id) => http.get(`${RESOURCE}/${id}`),
  preview: (contractId, periodMonth) =>
    http.get(`${RESOURCE}/preview`, { contract_id: contractId, period_month: periodMonth }),
  create: (payload) => http.post(RESOURCE, payload),
  assess: (id, payload) => http.post(`${RESOURCE}/${id}/assess`, payload),
  manual: (id, payload) => http.post(`${RESOURCE}/${id}/manual`, payload),
  transitions: (id) => http.get(`${RESOURCE}/${id}/transitions`),
  changeStatus: (id, payload) => http.post(`${RESOURCE}/${id}/transitions`, payload),
  updateRemark: (id, payload) => http.patch(`${RESOURCE}/${id}`, payload),
  remove: (id) => http.delete(`${RESOURCE}/${id}`),
  traceByInspection: (inspectionId) =>
    http.get(`${RESOURCE}/trace/inspection/${inspectionId}`),
  traceByIssue: (issueId) => http.get(`${RESOURCE}/trace/issue/${issueId}`),
};
