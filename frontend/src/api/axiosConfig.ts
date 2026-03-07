import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8890',
  timeout: 120000, // 120 seconds for deep analysis
});

// Response interceptor for global error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export default api;
