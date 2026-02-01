import axios from 'axios';

class APIError extends Error {
    constructor(message, statusCode, details) {
        super(message);
        this.name = 'APIError';
        this.statusCode = statusCode;
        this.details = details;
    }
}

// Environment configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1';
const REQUEST_TIMEOUT = parseInt(process.env.NEXT_PUBLIC_REQUEST_TIMEOUT || '30000');

// Create axios instance with default config
const apiClient = axios.create({
    baseURL: API_BASE_URL,
    timeout: REQUEST_TIMEOUT,
    headers: {
        'Content-Type': 'application/json',
    },
    withCredentials: false,
});

// Request interceptor to inject auth token
apiClient.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        
        // Add request ID for tracing
        config.headers['X-Request-ID'] = generateRequestId();
        
        return config;
    },
    (error) => {
        console.error('Request interceptor error:', error);
        return Promise.reject(error);
    }
);

// Response interceptor to handle common errors
apiClient.interceptors.response.use(
    (response) => {
        // You can transform response data here
        return response;
    },
    (error) => {
        if (error.code === 'ECONNABORTED') {
            return Promise.reject(new APIError('Request timeout', 408, error.config));
        }
        
        if (!error.response) {
            // Network error
            return Promise.reject(new APIError('Network error', 0, 'Unable to connect to server'));
        }
        
        const { status, data } = error.response;
        
        switch (status) {
            case 401:
                // Token expired or invalid
                localStorage.removeItem('access_token');
                localStorage.removeItem('user');
                window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
                break;
                
            case 403:
                // Permission denied
                return Promise.reject(new APIError('Permission denied', 403, data));
                
            case 404:
                // Resource not found
                return Promise.reject(new APIError('Resource not found', 404, data));
                
            case 429:
                // Rate limited
                return Promise.reject(new APIError('Rate limit exceeded', 429, data));
                
            case 500:
                // Server error
                return Promise.reject(new APIError('Server error', 500, data));
                
            default:
                return Promise.reject(new APIError(`Request failed with status ${status}`, status, data));
        }
        
        return Promise.reject(error);
    }
);

// Helper function to generate unique request ID
function generateRequestId() {
    return 'req_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// API methods
export const callAPI = {
    // Authentication
    login: async (credentials) => {
        try {
            const response = await apiClient.post('/auth/login', credentials);
            const { access_token, user } = response.data;
            
            // Store token and user data
            localStorage.setItem('access_token', access_token);
            localStorage.setItem('user', JSON.stringify(user));
            
            return { success: true, user };
        } catch (error) {
            console.error('Login error:', error);
            throw error;
        }
    },
    
    logout: () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
    },
    
    getCurrentUser: () => {
        const userStr = localStorage.getItem('user');
        return userStr ? JSON.parse(userStr) : null;
    },
    
    // Call Management
    uploadCall: async (formData, onProgress) => {
        try {
            const response = await apiClient.post('/calls/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
                onUploadProgress: onProgress || (() => {}),
            });
            return response.data;
        } catch (error) {
            console.error('Upload call error:', error);
            throw error;
        }
    },
    
    getCallStatus: async (callId) => {
        try {
            const response = await apiClient.get(`/calls/${callId}/status`);
            return response.data;
        } catch (error) {
            console.error('Get call status error:', error);
            throw error;
        }
    },
    
    getCallAnalysis: async (callId) => {
        try {
            const response = await apiClient.get(`/calls/${callId}/analysis`);
            return response.data;
        } catch (error) {
            console.error('Get call analysis error:', error);
            throw error;
        }
    },
    
    listCalls: async (params = {}) => {
        try {
            const response = await apiClient.get('/calls/', { params });
            return response.data;
        } catch (error) {
            console.error('List calls error:', error);
            throw error;
        }
    },
    
    // CRM Integration
    getCRMSettings: async () => {
        try {
            const response = await apiClient.get('/crm/settings');
            return response.data;
        } catch (error) {
            console.error('Get CRM settings error:', error);
            throw error;
        }
    },
    
    updateCRMSettings: async (settings) => {
        try {
            const response = await apiClient.post('/crm/settings', settings);
            return response.data;
        } catch (error) {
            console.error('Update CRM settings error:', error);
            throw error;
        }
    },
    
    testCRMConnection: async () => {
        try {
            const response = await apiClient.post('/crm/test');
            return response.data;
        } catch (error) {
            console.error('Test CRM connection error:', error);
            throw error;
        }
    },
    
    // Analytics
    getTeamMetrics: async (startDate, endDate) => {
        try {
            const response = await apiClient.get('/analytics/team', {
                params: { start_date: startDate, end_date: endDate }
            });
            return response.data;
        } catch (error) {
            console.error('Get team metrics error:', error);
            throw error;
        }
    },
    
    getUserPerformance: async (userId, period = 'month') => {
        try {
            const response = await apiClient.get(`/analytics/user/${userId}/performance`, {
                params: { period }
            });
            return response.data;
        } catch (error) {
            console.error('Get user performance error:', error);
            throw error;
        }
    },
    
    // Health check
    healthCheck: async () => {
        try {
            const response = await apiClient.get('/health');
            return response.data;
        } catch (error) {
            console.error('Health check error:', error);
            throw error;
        }
    }
};

// Export axios instance for custom requests
export default apiClient;

// Export error class
export { APIError };