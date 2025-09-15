/**
 * WebSocket Client for Real-time Status Updates
 * 
 * This module handles WebSocket connections and real-time updates
 * for manual check queue status and progress tracking.
 */

class WebSocketClient {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // Start with 1 second
        this.isConnected = false;
        this.messageHandlers = new Map();
        
        // Initialize connection
        this.connect();
    }
    
    connect() {
        try {
            const wsUrl = this.getWebSocketUrl();
            console.log('🔌 Connecting to WebSocket:', wsUrl);
            
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = (event) => {
                console.log('✅ WebSocket connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.reconnectDelay = 1000;
                this.triggerEvent('connected', event);
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('❌ Error parsing WebSocket message:', error);
                }
            };
            
            this.ws.onclose = (event) => {
                console.log('🔌 WebSocket disconnected:', event.code, event.reason);
                this.isConnected = false;
                this.triggerEvent('disconnected', event);
                this.scheduleReconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('❌ WebSocket error:', error);
                this.triggerEvent('error', error);
            };
            
        } catch (error) {
            console.error('❌ Error creating WebSocket connection:', error);
            this.scheduleReconnect();
        }
    }
    
    getWebSocketUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname;
        const port = window.location.port || (window.location.protocol === 'https:' ? '443' : '80');
        return `${protocol}//${host}:8765`;
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('❌ Max reconnection attempts reached');
            this.triggerEvent('maxReconnectAttemptsReached');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff
        
        console.log(`🔄 Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => {
            this.connect();
        }, delay);
    }
    
    handleMessage(data) {
        console.log('📨 WebSocket message received:', data);
        
        switch (data.type) {
            case 'connection':
                this.handleConnectionMessage(data);
                break;
            case 'status_update':
                this.handleStatusUpdate(data);
                break;
            case 'queue_update':
                this.handleQueueUpdate(data);
                break;
            case 'pong':
                this.handlePong(data);
                break;
            default:
                console.warn('⚠️ Unknown message type:', data.type);
        }
    }
    
    handleConnectionMessage(data) {
        console.log('🔌 Connection message:', data.message);
        this.triggerEvent('connectionMessage', data);
    }
    
    handleStatusUpdate(data) {
        console.log('📊 Status update:', data);
        this.triggerEvent('statusUpdate', data);
        this.updateUIStatus(data);
    }
    
    handleQueueUpdate(data) {
        console.log('📋 Queue update:', data);
        this.triggerEvent('queueUpdate', data);
        this.updateQueueDisplay(data);
    }
    
    handlePong(data) {
        console.log('🏓 Pong received');
        this.triggerEvent('pong', data);
    }
    
    updateUIStatus(data) {
        const { queue_id, status, message } = data;
        
        // Update button status
        const button = document.querySelector(`[data-queue-id="${queue_id}"]`);
        if (button) {
            this.updateButtonStatus(button, status, message);
        }
        
        // Update status display
        const statusElement = document.querySelector(`[data-status-id="${queue_id}"]`);
        if (statusElement) {
            this.updateStatusDisplay(statusElement, status, message);
        }
    }
    
    updateButtonStatus(button, status, message) {
        const originalText = button.dataset.originalText || button.textContent;
        
        switch (status) {
            case 'pending':
                button.disabled = true;
                button.innerHTML = '<i class="bi bi-clock"></i> In Queue';
                button.className = 'btn btn-warning btn-sm';
                break;
            case 'processing':
                button.disabled = true;
                button.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i> Processing';
                button.className = 'btn btn-info btn-sm';
                break;
            case 'completed':
                button.disabled = false;
                button.innerHTML = originalText;
                button.className = 'btn btn-success btn-sm';
                setTimeout(() => {
                    button.className = button.dataset.originalClass || 'btn btn-primary btn-sm';
                }, 3000);
                break;
            case 'failed':
                button.disabled = false;
                button.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Failed';
                button.className = 'btn btn-danger btn-sm';
                setTimeout(() => {
                    button.innerHTML = originalText;
                    button.className = button.dataset.originalClass || 'btn btn-primary btn-sm';
                }, 5000);
                break;
        }
    }
    
    updateStatusDisplay(element, status, message) {
        const statusClass = this.getStatusClass(status);
        const statusIcon = this.getStatusIcon(status);
        
        element.innerHTML = `
            <span class="badge ${statusClass}">
                <i class="bi ${statusIcon}"></i> ${status.charAt(0).toUpperCase() + status.slice(1)}
            </span>
            <small class="text-muted ms-2">${message}</small>
        `;
    }
    
    updateQueueDisplay(data) {
        const queueContainer = document.getElementById('queue-status');
        if (!queueContainer) return;
        
        const queue = data.queue || [];
        const pendingCount = queue.filter(item => item.status === 'pending').length;
        const processingCount = queue.filter(item => item.status === 'processing').length;
        
        queueContainer.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <small class="text-muted">
                        <i class="bi bi-clock"></i> Pending: ${pendingCount}
                    </small>
                </div>
                <div class="col-md-6">
                    <small class="text-muted">
                        <i class="bi bi-arrow-clockwise"></i> Processing: ${processingCount}
                    </small>
                </div>
            </div>
        `;
    }
    
    getStatusClass(status) {
        const classes = {
            'pending': 'bg-warning',
            'processing': 'bg-info',
            'completed': 'bg-success',
            'failed': 'bg-danger'
        };
        return classes[status] || 'bg-secondary';
    }
    
    getStatusIcon(status) {
        const icons = {
            'pending': 'bi-clock',
            'processing': 'bi-arrow-clockwise',
            'completed': 'bi-check-circle',
            'failed': 'bi-exclamation-triangle'
        };
        return icons[status] || 'bi-question-circle';
    }
    
    sendMessage(message) {
        if (this.isConnected && this.ws) {
            this.ws.send(JSON.stringify(message));
        } else {
            console.warn('⚠️ WebSocket not connected, cannot send message');
        }
    }
    
    ping() {
        this.sendMessage({ type: 'ping' });
    }
    
    subscribe(subscription) {
        this.sendMessage({ type: 'subscribe', subscription });
    }
    
    on(event, handler) {
        if (!this.messageHandlers.has(event)) {
            this.messageHandlers.set(event, []);
        }
        this.messageHandlers.get(event).push(handler);
    }
    
    off(event, handler) {
        if (this.messageHandlers.has(event)) {
            const handlers = this.messageHandlers.get(event);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }
    
    triggerEvent(event, data) {
        if (this.messageHandlers.has(event)) {
            this.messageHandlers.get(event).forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error('❌ Error in event handler:', error);
                }
            });
        }
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.isConnected = false;
    }
}

// Global WebSocket client instance
window.websocketClient = new WebSocketClient();

// Auto-ping every 30 seconds to keep connection alive
setInterval(() => {
    if (window.websocketClient && window.websocketClient.isConnected) {
        window.websocketClient.ping();
    }
}, 30000);

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebSocketClient;
}
