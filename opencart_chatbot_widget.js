/**
 * OpenCart AI Chatbot Widget
 * Displays a Jivo-like messenger bubble with AI-powered product search
 * Uses DeepSeek LLM for intelligent responses
 * 
 * Usage:
 * <script>
 *   window.GraphTalkChatbot = {
 *     apiKey: 'wk_N7WsBd1_cGsbgLI7DFihlK5KfLO80pxI5JZ9uqH1mwE',
 *     catalogId: 'demo-catalog',
 *     apiEndpoint: 'http://localhost:9001',
 *     deepseekApiKey: 'sk_...', // DeepSeek API key for LLM
 *     position: 'bottom-right' // or 'bottom-left'
 *   };
 * </script>
 * <script src="opencart_chatbot_widget.js"></script>
 */

(function() {
  'use strict';

  // Configuration from window object
  const config = window.GraphTalkChatbot || {};
  const API_KEY = config.apiKey || 'e5adee97-1536-45bd-97e9-e647173f07d7'; // Fallback to valid session
  const DEEPSEEK_API_KEY = config.deepseekApiKey;
  const CATALOG_ID = config.catalogId || 'opencart-catalog';
  const API_ENDPOINT = config.apiEndpoint || 'http://localhost:9001';
  const POSITION = config.position || 'bottom-right';

  if (!API_KEY) {
    console.error('GraphTalkChatbot: API key not configured. Set window.GraphTalkChatbot.apiKey');
    return;
  }

  if (!DEEPSEEK_API_KEY) {
    console.warn('GraphTalkChatbot: DeepSeek API key not configured. Using GraphTalk API only.');
  }

  // CSS for the widget
  const CSS = `
    .graphtalk-chatbot-bubble {
      position: fixed;
      ${POSITION === 'bottom-left' ? 'left: 20px;' : 'right: 20px;'}
      bottom: 20px;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 9998;
      transition: all 0.3s ease;
      font-size: 28px;
    }

    .graphtalk-chatbot-bubble:hover {
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
      transform: scale(1.1);
    }

    .graphtalk-chatbot-bubble.active {
      background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
    }

    .graphtalk-chatbot-container {
      position: fixed;
      ${POSITION === 'bottom-left' ? 'left: 20px;' : 'right: 20px;'}
      bottom: 90px;
      width: 380px;
      height: 600px;
      background: white;
      border-radius: 12px;
      box-shadow: 0 5px 40px rgba(0, 0, 0, 0.16);
      display: none;
      flex-direction: column;
      z-index: 9999;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
      overflow: hidden;
    }

    .graphtalk-chatbot-container.active {
      display: flex;
    }

    .graphtalk-chatbot-header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid rgba(0, 0, 0, 0.1);
    }

    .graphtalk-chatbot-header h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
    }

    .graphtalk-chatbot-header-subtitle {
      font-size: 12px;
      opacity: 0.9;
      margin-top: 4px;
    }

    .graphtalk-chatbot-header-subtitle code {
      background: rgba(255, 255, 255, 0.2);
      padding: 2px 6px;
      border-radius: 3px;
      font-family: 'Courier New', monospace;
      font-weight: 600;
      font-size: 11px;
    }

    .graphtalk-chatbot-close {
      background: none;
      border: none;
      color: white;
      font-size: 24px;
      cursor: pointer;
      padding: 0;
      width: 30px;
      height: 30px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s;
    }

    .graphtalk-chatbot-close:hover {
      transform: rotate(90deg);
    }

    .graphtalk-chatbot-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      background: #f7f7f7;
    }

    .graphtalk-chatbot-message {
      display: flex;
      margin-bottom: 8px;
      animation: slideIn 0.3s ease;
    }

    @keyframes slideIn {
      from {
        opacity: 0;
        transform: translateY(10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .graphtalk-chatbot-message.user {
      justify-content: flex-end;
    }

    .graphtalk-chatbot-message-content {
      max-width: 80%;
      padding: 10px 14px;
      border-radius: 12px;
      font-size: 14px;
      line-height: 1.4;
      word-wrap: break-word;
    }

    .graphtalk-chatbot-message.bot .graphtalk-chatbot-message-content {
      background: white;
      color: #333;
      border: 1px solid #e0e0e0;
    }

    .graphtalk-chatbot-message.streaming .graphtalk-chatbot-message-content {
      background: white;
      color: #333;
      border: 1px solid #e0e0e0;
      position: relative;
    }

    .graphtalk-chatbot-message.streaming .graphtalk-chatbot-message-content::after {
      content: '';
      display: inline-block;
      width: 2px;
      height: 1.2em;
      background: #667eea;
      animation: cursor 1s infinite;
      margin-left: 2px;
      vertical-align: text-bottom;
    }

    @keyframes cursor {
      0%, 50% { opacity: 1; }
      51%, 100% { opacity: 0; }
    }

    .graphtalk-chatbot-message.user .graphtalk-chatbot-message-content {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
    }

    .graphtalk-chatbot-message.bot.loading .graphtalk-chatbot-message-content {
      background: white;
    }

    .graphtalk-chatbot-typing {
      display: flex;
      gap: 4px;
      align-items: center;
    }

    .graphtalk-chatbot-typing span {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #667eea;
      animation: typing 1.4s infinite;
    }

    .graphtalk-chatbot-typing span:nth-child(2) {
      animation-delay: 0.2s;
    }

    .graphtalk-chatbot-typing span:nth-child(3) {
      animation-delay: 0.4s;
    }

    @keyframes typing {
      0%, 60%, 100% {
        opacity: 0.5;
        transform: translateY(0);
      }
      30% {
        opacity: 1;
        transform: translateY(-10px);
      }
    }

    .graphtalk-chatbot-input-area {
      padding: 12px;
      border-top: 1px solid #e0e0e0;
      display: flex;
      gap: 8px;
      background: white;
    }

    .graphtalk-chatbot-input {
      flex: 1;
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 14px;
      font-family: inherit;
      resize: none;
      max-height: 100px;
      outline: none;
      transition: border-color 0.2s;
    }

    .graphtalk-chatbot-input:focus {
      border-color: #667eea;
      box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }

    .graphtalk-chatbot-send-btn {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      border: none;
      border-radius: 8px;
      padding: 10px 16px;
      cursor: pointer;
      font-size: 16px;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      justify-content: center;
      min-width: 40px;
    }

    .graphtalk-chatbot-send-btn:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }

    .graphtalk-chatbot-send-btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    .graphtalk-chatbot-welcome {
      text-align: center;
      padding: 20px;
      color: #666;
      font-size: 14px;
      line-height: 1.6;
    }

    .graphtalk-chatbot-welcome h4 {
      margin: 0 0 12px 0;
      color: #333;
      font-size: 16px;
    }

    .graphtalk-chatbot-welcome p {
      margin: 0 0 12px 0;
    }

    .graphtalk-chatbot-quick-actions {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-top: 12px;
    }

    .graphtalk-chatbot-quick-btn {
      background: #f0f0f0;
      border: 1px solid #ddd;
      border-radius: 6px;
      padding: 10px 12px;
      cursor: pointer;
      font-size: 13px;
      transition: all 0.2s;
      text-align: left;
    }

    .graphtalk-chatbot-quick-btn:hover {
      background: #e8e8e8;
      border-color: #667eea;
    }

    .graphtalk-chatbot-error {
      background: #fee;
      color: #c33;
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 13px;
      border: 1px solid #fcc;
    }

    .graphtalk-chatbot-badge {
      position: absolute;
      top: -5px;
      right: -5px;
      background: #ff4757;
      color: white;
      border-radius: 50%;
      width: 24px;
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      font-weight: bold;
    }

    @media (max-width: 480px) {
      .graphtalk-chatbot-container {
        width: calc(100% - 40px);
        height: 70vh;
        max-height: 600px;
      }
    }
  `;

  // Initialize widget
  function initWidget() {
    // Inject CSS
    const styleElement = document.createElement('style');
    styleElement.textContent = CSS;
    document.head.appendChild(styleElement);

    // Create HTML
    const container = document.createElement('div');
    container.innerHTML = `
      <div class="graphtalk-chatbot-bubble" id="graphtalk-bubble" title="Chat with AI">💬</div>
      
      <div class="graphtalk-chatbot-container" id="graphtalk-container">
        <div class="graphtalk-chatbot-header">
          <div>
            <h3>AI Assistant</h3>
            <div class="graphtalk-chatbot-header-subtitle">
              <span style="font-size: 12px; opacity: 0.9; display: block; margin-top: 2px;">Catalog ID:</span>
              <code style="background: rgba(255,255,255,0.2); padding: 3px 6px; border-radius: 4px; font-size: 11px; word-break: break-all;">${CATALOG_ID}</code>
              <button id="copy-catalog-id" style="background: rgba(255,255,255,0.2); border: none; color: white; border-radius: 4px; padding: 2px 6px; margin-left: 5px; font-size: 11px; cursor: pointer; transition: background 0.2s;">📋</button>
            </div>
          </div>
          <button class="graphtalk-chatbot-close" id="graphtalk-close">×</button>
        </div>
        
        <div class="graphtalk-chatbot-messages" id="graphtalk-messages">
          <div class="graphtalk-chatbot-message bot">
            <div class="graphtalk-chatbot-message-content">
              <div class="graphtalk-chatbot-welcome">
                <h4>Welcome! 👋</h4>
                <p>Ask me about our products. I'll provide AI-generated summaries based on your search.</p>
                <div class="graphtalk-chatbot-quick-actions">
                  <button class="graphtalk-chatbot-quick-btn" data-query="high performance laptops">High Performance Laptops</button>
                  <button class="graphtalk-chatbot-quick-btn" data-query="wireless headphones">Wireless Headphones</button>
                  <button class="graphtalk-chatbot-quick-btn" data-query="smartphones">Smartphones</button>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="graphtalk-chatbot-input-area">
          <input 
            type="text" 
            class="graphtalk-chatbot-input" 
            id="graphtalk-input" 
            placeholder="Ask about products..."
            autocomplete="off"
          />
          <button class="graphtalk-chatbot-send-btn" id="graphtalk-send">📤</button>
        </div>
      </div>
    `;

    document.body.appendChild(container);

    // Get elements
    const bubble = document.getElementById('graphtalk-bubble');
    const chatContainer = document.getElementById('graphtalk-container');
    const closeBtn = document.getElementById('graphtalk-close');
    const messagesDiv = document.getElementById('graphtalk-messages');
    const inputField = document.getElementById('graphtalk-input');
    const sendBtn = document.getElementById('graphtalk-send');
    const quickBtns = document.querySelectorAll('.graphtalk-chatbot-quick-btn');

    // Add copy functionality for catalog ID
    document.getElementById('copy-catalog-id')?.addEventListener('click', (e) => {
      e.stopPropagation();
      navigator.clipboard.writeText(CATALOG_ID);
      const button = e.target;
      const originalText = button.textContent;
      button.textContent = '✅';
      button.style.background = 'rgba(76, 175, 80, 0.3)';
      setTimeout(() => {
        button.textContent = originalText;
        button.style.background = 'rgba(255,255,255,0.2)';
      }, 2000);
    });

    // Event listeners
    bubble.addEventListener('click', () => {
      chatContainer.classList.toggle('active');
      bubble.classList.toggle('active');
      if (chatContainer.classList.contains('active')) {
        inputField.focus();
      }
    });

    closeBtn.addEventListener('click', () => {
      chatContainer.classList.remove('active');
      bubble.classList.remove('active');
    });

    inputField.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    sendBtn.addEventListener('click', sendMessage);

    quickBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const query = btn.getAttribute('data-query');
        inputField.value = query;
        sendMessage();
      });
    });

    // WebSocket connection
    let websocket = null;
    let connectionAttempts = 0;
    const maxConnectionAttempts = 3;
    
    function initWebSocket() {
      if (websocket && websocket.readyState === WebSocket.OPEN) {
        return websocket;
      }
      
      const wsUrl = `${API_ENDPOINT.replace('http', 'ws')}/ws/query?token=${API_KEY}`;
      console.log('Connecting to WebSocket:', wsUrl);
      
      try {
        websocket = new WebSocket(wsUrl);
        
        websocket.onopen = () => {
          console.log('WebSocket connected successfully');
          connectionAttempts = 0;
        };
        
        websocket.onclose = () => {
          console.log('WebSocket disconnected');
          websocket = null;
        };
        
        websocket.onerror = (error) => {
          console.error('WebSocket error:', error);
          websocket = null;
        };
        
      } catch (error) {
        console.error('Failed to create WebSocket:', error);
        websocket = null;
      }
      
      return websocket;
    }
    
    // Send message function with WebSocket streaming
    async function sendMessage() {
      const message = inputField.value.trim();
      if (!message) return;

      // Add user message
      addMessage(message, 'user');
      inputField.value = '';
      inputField.focus();
      sendBtn.disabled = true;

      // Initialize WebSocket connection
      if (!websocket || websocket.readyState !== WebSocket.OPEN) {
        if (connectionAttempts >= maxConnectionAttempts) {
          addMessage(
            '❌ Unable to connect to chat service. Please refresh the page and try again.',
            'bot error'
          );
          sendBtn.disabled = false;
          return;
        }
        
        initWebSocket();
        connectionAttempts++;
        
        // Wait for connection
        await new Promise((resolve) => {
          const checkConnection = () => {
            if (websocket && websocket.readyState === WebSocket.OPEN) {
              resolve();
            } else if (websocket && websocket.readyState === WebSocket.CLOSED) {
              resolve();
            } else {
              setTimeout(checkConnection, 100);
            }
          };
          checkConnection();
        });
        
        if (!websocket || websocket.readyState !== WebSocket.OPEN) {
          addMessage(
            '❌ Failed to connect to chat service. Please try again.',
            'bot error'
          );
          sendBtn.disabled = false;
          return;
        }
      }

      // Show loading and streaming indicators
      const loadingId = addMessage('', 'bot loading');
      let streamingMessageId = null;
      let accumulatedResponse = '';

      try {
        // Send WebSocket message
        const wsMessage = {
          question: message,
          humanize: true,
          stream: true,
          session_id: `widget-${Date.now()}`
        };
        
        websocket.send(JSON.stringify(wsMessage));
        console.log('WebSocket message sent:', wsMessage);

        // Set up message handler for this specific query
        let messageHandlerActive = true;
        const messageHandler = (event) => {
          if (!messageHandlerActive) return;
          
          try {
            const data = JSON.parse(event.data);
            
            switch (data.type) {
              case 'status':
                console.log('Status:', data.message);
                // Update loading message if needed
                const loadingElement = document.getElementById(loadingId);
                if (loadingElement && data.message) {
                  const contentDiv = loadingElement.querySelector('.graphtalk-chatbot-message-content');
                  if (contentDiv) {
                    // Show specific status messages with better formatting
                    const displayMessage = data.message.includes('Generating AI analysis') 
                      ? '🤖 Generating AI analysis...' 
                      : data.message;
                    
                    contentDiv.innerHTML = `
                      <div class="graphtalk-chatbot-typing">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                      <div style="font-size: 12px; margin-top: 8px; color: #666; font-weight: 500;">${displayMessage}</div>
                    `;
                  }
                }
                break;
                
              case 'immediate':
                // Handle immediate search results (optional - show as context)
                const files = data.data?.files || [];
                if (files.length > 0) {
                  console.log('Found relevant files:', files);
                }
                break;
                
              case 'stream_start':
                // Remove loading, start streaming
                removeMessage(loadingId);
                streamingMessageId = addMessage('', 'bot streaming');
                console.log('Streaming started - AI overview generation begun');
                break;
                
              case 'stream_token':
                // Add token to streaming response
                if (streamingMessageId) {
                  accumulatedResponse += data.token;
                  updateStreamingMessage(streamingMessageId, accumulatedResponse);
                }
                break;
                
              case 'stream_end':
                // Streaming completed
                console.log('Streaming completed');
                if (streamingMessageId) {
                  // Convert streaming message to normal message
                  const streamingElement = document.getElementById(streamingMessageId);
                  if (streamingElement) {
                    streamingElement.classList.remove('streaming');
                    streamingElement.classList.add('bot');
                  }
                }
                
                // Deactivate this message handler
                messageHandlerActive = false;
                sendBtn.disabled = false;
                break;
                
              case 'overview':
                // Non-streaming fallback
                removeMessage(loadingId);
                addMessage(data.data, 'bot');
                messageHandlerActive = false;
                sendBtn.disabled = false;
                break;
                
              case 'error':
                // Handle errors
                removeMessage(loadingId);
                if (streamingMessageId) {
                  removeMessage(streamingMessageId);
                }
                addMessage(
                  `❌ Error: ${data.message || 'Something went wrong. Please try again.'}`,
                  'bot error'
                );
                messageHandlerActive = false;
                sendBtn.disabled = false;
                break;
                
              default:
                console.log('Unhandled message type:', data.type, data);
            }
          } catch (error) {
            console.error('Error processing WebSocket message:', error);
          }
        };

        // Add message handler
        websocket.addEventListener('message', messageHandler);

        // Set timeout for fallback and also check if streaming started
        setTimeout(() => {
          if (messageHandlerActive) {
            // Check if we're still in loading state (streaming never started)
            if (document.getElementById(loadingId)) {
              removeMessage(loadingId);
              addMessage(
                '⚠️ AI analysis is taking longer than expected. This might be due to high demand or API issues. Please try again in a moment.',
                'bot error'
              );
              messageHandlerActive = false;
              sendBtn.disabled = false;
            }
            // If streaming started but never completed
            else if (streamingMessageId && document.getElementById(streamingMessageId)) {
              const streamingElement = document.getElementById(streamingMessageId);
              const contentDiv = streamingElement.querySelector('.graphtalk-chatbot-message-content');
              if (contentDiv && contentDiv.textContent.trim() === '') {
                // Streaming started but no content received
                removeMessage(streamingMessageId);
                addMessage(
                  '⚠️ AI response was incomplete. Please try your query again.',
                  'bot error'
                );
              } else {
                // Convert partial response to normal message
                streamingElement.classList.remove('streaming');
                streamingElement.classList.add('bot');
                addMessage(
                  '⚠️ AI response was cut short. The partial response above may still be helpful.',
                  'bot'
                );
              }
              messageHandlerActive = false;
              sendBtn.disabled = false;
            }
          }
        }, 30000); // 30 second timeout

      } catch (error) {
        removeMessage(loadingId);
        if (streamingMessageId) {
          removeMessage(streamingMessageId);
        }
        console.error('WebSocket Error:', error);
        addMessage(
          `❌ Error: ${error.message || 'Failed to send message. Please try again.'}`,
          'bot error'
        );
        sendBtn.disabled = false;
      }
    }

    // Helper functions
    function addMessage(text, type) {
      const messageDiv = document.createElement('div');
      messageDiv.className = `graphtalk-chatbot-message ${type}`;
      messageDiv.id = `msg-${Date.now()}`;

      const contentDiv = document.createElement('div');
      contentDiv.className = 'graphtalk-chatbot-message-content';

      if (type === 'bot loading') {
        contentDiv.innerHTML = `
          <div class="graphtalk-chatbot-typing">
            <span></span>
            <span></span>
            <span></span>
          </div>
        `;
      } else if (type === 'bot error') {
        contentDiv.className += ' graphtalk-chatbot-error';
        contentDiv.textContent = text;
      } else {
        contentDiv.textContent = text;
      }

      messageDiv.appendChild(contentDiv);
      messagesDiv.appendChild(messageDiv);
      messagesDiv.scrollTop = messagesDiv.scrollHeight;

      return messageDiv.id;
    }

    function updateStreamingMessage(id, text) {
      const element = document.getElementById(id);
      if (element) {
        const contentDiv = element.querySelector('.graphtalk-chatbot-message-content');
        if (contentDiv) {
          contentDiv.textContent = text;
          // Scroll to bottom as new content arrives
          const messagesDiv = element.parentElement;
          if (messagesDiv) {
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
          }
        }
      }
    }

    function removeMessage(id) {
      const element = document.getElementById(id);
      if (element) {
        element.remove();
      }
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initWidget);
  } else {
    initWidget();
  }
})();
