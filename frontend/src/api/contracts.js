import { http } from './client.js';

const RESOURCE = '/contracts';

export const contractApi = {
  list: (params) => http.get(RESOURCE, params),
  detail: (id) => http.get(`${RESOURCE}/${id}`),
  create: (payload) => http.post(RESOURCE, payload),
  update: (id, payload) => http.patch(`${RESOURCE}/${id}`, payload),
  terminate: (id, payload) => http.post(`${RESOURCE}/${id}/terminate`, payload),
  remove: (id) => http.delete(`${RESOURCE}/${id}`),
  assessmentPreview: (id, params) => http.get(`${RESOURCE}/${id}/assessment-preview`, params),
  createSettlement: (id, payload) => http.post(`${RESOURCE}/${id}/settlements`, payload),
};
