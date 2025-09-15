/**
 * Queue Manager for Manual Checks
 * 
 * This module handles manual check requests, queue status updates,
 * and UI interactions for the queue system.
 */

class QueueManager {
    constructor() {
        this.websocketClient = window.websocketClient;
        this.activeChecks = new Map(); // Track active checks by website ID
        this.init();
    }
    
    init() {
        // Set up WebSocket event handlers
        this.websocketClient.on('statusUpdate', (data) => {
            this.handleStatusUpdate(data);
        });
        
        this.websocketClient.on('queueUpdate', (data) => {
            this.handleQueueUpdate(data);
        });
        
        this.websocketClient.on('connected', () => {
            this.updateConnectionStatus(true);
        });
        
        this.websocketClient.on('disconnected', () => {
            this.updateConnectionStatus(false);
        });
        
        // Set up button event listeners
        this.setupButtonListeners();
        
        // Initial queue status update
        this.updateQueueStatus();
    }
    
    setupButtonListeners() {
        // Manual check buttons
        document.addEventListener('click', (event) => {
            if (event.target.matches('[data-check-type]')) {
                event.preventDefault();
                this.handleManualCheck(event.target);
            }
        });
        
        // Refresh queue status button
        const refreshBtn = document.getElementById('refresh-queue');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.updateQueueStatus();
            });
        }
    }
    
    async handleManualCheck(button) {
        const websiteId = button.dataset.websiteId;
        const checkType = button.dataset.checkType;
        const form = button.closest('form');
        
        if (!websiteId || !checkType) {
            console.error('❌ Missing website ID or check type');
            return;
        }
        
        // Check if button is already disabled (prevent multiple clicks)
        if (button.disabled) {
            console.log('Button already disabled, ignoring click');
            return;
        }
        
        // Check if already processing
        if (this.activeChecks.has(websiteId)) {
            this.showMessage('Check already in progress for this website', 'warning');
            return;
        }
        
        try {
            // Disable button immediately to prevent multiple clicks
            button.disabled = true;
            
            // Store original button state
            this.storeButtonState(button);
            
            // Show loading state
            this.setButtonLoading(button, true);
            
            // Prepare JSON data
            const requestData = {
                check_type: checkType
            };
            
            // Add baseline creation flag if needed
            if (checkType === 'baseline') {
                requestData.create_baseline = true;
            }
            
            // Send request
            const response = await fetch(`/website/${websiteId}/manual_check`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                // Track active check
                this.activeChecks.set(websiteId, {
                    queueId: result.queue_id,
                    checkType: checkType,
                    button: button
                });
                
                // Update button with queue info
                this.setButtonQueued(button, result);
                
                this.showMessage(result.message, 'success');
                
                // Subscribe to updates for this check
                this.websocketClient.subscribe(`check_${result.queue_id}`);
                
            } else {
                this.setButtonError(button, result.message);
                this.showMessage(result.message, 'danger');
            }
            
        } catch (error) {
            console.error('❌ Error triggering manual check:', error);
            this.setButtonError(button, 'Network error');
            this.showMessage('Failed to trigger check: ' + error.message, 'danger');
        }
    }
    
    handleStatusUpdate(data) {
        const { queue_id, status, message } = data;
        
        // Find the check by queue ID
        for (const [websiteId, checkInfo] of this.activeChecks.entries()) {
            if (checkInfo.queueId === queue_id) {
                this.updateCheckStatus(websiteId, checkInfo, status, message);
                break;
            }
        }
    }
    
    handleQueueUpdate(data) {
        this.updateQueueDisplay(data);
    }
    
    updateCheckStatus(websiteId, checkInfo, status, message) {
        const { button } = checkInfo;
        
        switch (status) {
            case 'processing':
                this.setButtonProcessing(button, message);
                break;
            case 'completed':
                this.setButtonCompleted(button, message);
                this.activeChecks.delete(websiteId);
                this.showMessage(`Check completed: ${message}`, 'success');
                break;
            case 'failed':
                this.setButtonFailed(button, message);
                this.activeChecks.delete(websiteId);
                this.showMessage(`Check failed: ${message}`, 'danger');
                break;
        }
    }
    
    storeButtonState(button) {
        if (!button.dataset.originalText) {
            button.dataset.originalText = button.textContent;
        }
        if (!button.dataset.originalClass) {
            button.dataset.originalClass = button.className;
        }
    }
    
    setButtonLoading(button, loading) {
        if (loading) {
            button.disabled = true;
            button.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i> Loading...';
            button.className = 'btn btn-secondary btn-sm';
        } else {
            button.disabled = false;
            button.innerHTML = button.dataset.originalText;
            button.className = button.dataset.originalClass;
        }
    }
    
    setButtonQueued(button, result) {
        button.disabled = true;
        button.innerHTML = '<i class="bi bi-clock"></i> In Queue';
        button.className = 'btn btn-warning btn-sm';
        button.dataset.queueId = result.queue_id;
        
        // Add position info if available
        if (result.position !== undefined) {
            button.title = `Position ${result.position + 1} in queue`;
        }
    }
    
    setButtonProcessing(button, message) {
        button.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i> Processing';
        button.className = 'btn btn-info btn-sm';
        button.title = message;
    }
    
    setButtonCompleted(button, message) {
        button.innerHTML = '<i class="bi bi-check-circle"></i> Completed';
        button.className = 'btn btn-success btn-sm';
        button.disabled = false;
        
        // Reset after 3 seconds
        setTimeout(() => {
            button.innerHTML = button.dataset.originalText;
            button.className = button.dataset.originalClass;
            button.title = '';
            delete button.dataset.queueId;
        }, 3000);
    }
    
    setButtonFailed(button, message) {
        button.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Failed';
        button.className = 'btn btn-danger btn-sm';
        button.disabled = false;
        button.title = message;
        
        // Reset after 5 seconds
        setTimeout(() => {
            button.innerHTML = button.dataset.originalText;
            button.className = button.dataset.originalClass;
            button.title = '';
            delete button.dataset.queueId;
        }, 5000);
    }
    
    setButtonError(button, message) {
        button.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Error';
        button.className = 'btn btn-danger btn-sm';
        button.disabled = false;
        button.title = message;
        
        // Reset after 3 seconds
        setTimeout(() => {
            button.innerHTML = button.dataset.originalText;
            button.className = button.dataset.originalClass;
            button.title = '';
        }, 3000);
    }
    
    async updateQueueStatus() {
        try {
            const response = await fetch('/api/queue/status');
            const result = await response.json();
            
            if (result.status === 'success') {
                this.updateQueueDisplay(result);
            } else {
                console.error('❌ Error fetching queue status:', result.message);
            }
        } catch (error) {
            console.error('❌ Error fetching queue status:', error);
        }
    }
    
    updateQueueDisplay(data) {
        const queueContainer = document.getElementById('queue-status');
        if (!queueContainer) return;
        
        const queue = data.queue || [];
        const pendingCount = queue.filter(item => item.status === 'pending').length;
        const processingCount = queue.filter(item => item.status === 'processing').length;
        const completedCount = queue.filter(item => item.status === 'completed').length;
        const failedCount = queue.filter(item => item.status === 'failed').length;
        
        queueContainer.innerHTML = `
            <div class="row g-2">
                <div class="col-3">
                    <div class="text-center">
                        <div class="h5 mb-0 text-warning">${pendingCount}</div>
                        <small class="text-muted">Pending</small>
                    </div>
                </div>
                <div class="col-3">
                    <div class="text-center">
                        <div class="h5 mb-0 text-info">${processingCount}</div>
                        <small class="text-muted">Processing</small>
                    </div>
                </div>
                <div class="col-3">
                    <div class="text-center">
                        <div class="h5 mb-0 text-success">${completedCount}</div>
                        <small class="text-muted">Completed</small>
                    </div>
                </div>
                <div class="col-3">
                    <div class="text-center">
                        <div class="h5 mb-0 text-danger">${failedCount}</div>
                        <small class="text-muted">Failed</small>
                    </div>
                </div>
            </div>
        `;
    }
    
    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('websocket-status');
        if (statusElement) {
            if (connected) {
                statusElement.innerHTML = '<i class="bi bi-wifi text-success"></i> Connected';
                statusElement.className = 'badge bg-success';
            } else {
                statusElement.innerHTML = '<i class="bi bi-wifi-off text-danger"></i> Disconnected';
                statusElement.className = 'badge bg-danger';
            }
        }
    }
    
    showMessage(message, type = 'info') {
        // Create or update message container
        let container = document.getElementById('message-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'message-container';
            container.className = 'position-fixed top-0 end-0 p-3';
            container.style.zIndex = '1050';
            document.body.appendChild(container);
        }
        
        // Create message element
        const messageElement = document.createElement('div');
        messageElement.className = `alert alert-${type} alert-dismissible fade show`;
        messageElement.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        container.appendChild(messageElement);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (messageElement.parentNode) {
                messageElement.remove();
            }
        }, 5000);
    }
}

// Initialize queue manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.queueManager = new QueueManager();
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = QueueManager;
}
