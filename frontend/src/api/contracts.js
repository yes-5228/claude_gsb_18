import { http } from './client.js';

const RESOURCE = '/contracts';

export const contractApi = {
  list: (params) => http.get(RESOURCE, params),
  detail: (id) => http.get(`${RESOURCE}/${id}`),
  create: (payload) => http.post(RESOURCE, payload),
  update: (id, payload) => http.patch(`${RESOURCE}/${id}`, payload),
  remove: (id) => http.delete(`${RESOURCE}/${id}`),
  covering: (restroomId) => http.get(`${RESOURCE}/covering/${restroomId}`),
};
