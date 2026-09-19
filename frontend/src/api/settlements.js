import { http } from './client.js';

const RESOURCE = '/settlements';

export const settlementApi = {
  list: (params) => http.get(RESOURCE, params),
  detail: (id) => http.get(`${RESOURCE}/${id}`),
  reassess: (id) => http.post(`${RESOURCE}/${id}/reassess`),
  adjust: (id, payload) => http.patch(`${RESOURCE}/${id}`, payload),
  confirm: (id, payload) => http.post(`${RESOURCE}/${id}/confirm`, payload),
  remove: (id) => http.delete(`${RESOURCE}/${id}`),
};

export const issueTraceApi = {
  settlements: (issueId) => http.get(`/issues/${issueId}/settlements`),
};
