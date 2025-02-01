import React, { useState, useRef, useEffect } from 'react';
import { Message } from '../types/types';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';

interface ChatProps {
  onTicketCreated: (ticketData: any) => void;
}

const Chat: React.FC<ChatProps> = ({ onTicketCreated }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const quickActions = [
    { title: "Open Incident", payload: "/open_incident" },
    { title: "Check Incident Status", payload: "/incident_status" },
    { title: "Reset Password", payload: "/password_reset" },
    { title: "Email Problems", payload: "/problem_email" },
    { title: "Help", payload: "/help" }
  ];

  const sendMessage = async (text: string) => {
    const userMessage: Message = {
      id: Date.now() + Math.random().toString(36).substr(2, 9),
      text,
      sender: 'user'
    };
    
    setMessages(prev => [...prev, userMessage]);

    try {
      const response = await fetch('http://localhost:5005/webhooks/rest/webhook', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          sender: "user",
          message: text 
        }),
      });

      const data = await response.json();
      
      data.forEach((botReply: any) => {
        const botMessage: Message = {
          id: Date.now() + Math.random().toString(36).substr(2, 9),
          text: botReply.text,
          sender: 'bot',
          buttons: botReply.buttons
        };
        setMessages(prev => [...prev, botMessage]);
      });

      // If a ticket was created, refresh the ticket list
      if (text.includes('/create_incident') || text.includes('/send_to_helpdesk')) {
        onTicketCreated({ /* your ticket data here */ });
      }
    } catch (error) {
      console.error('Error sending message:', error);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white bg-opacity-90">
      <div className="bg-blue-600 text-white p-4">
        <h1 className="text-xl font-bold">OutreachX</h1>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4">
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} onButtonClick={sendMessage} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-gray-200 p-4 bg-white">
        <div className="flex flex-wrap gap-2 mb-4">
          {quickActions.map((action) => (
            <button
              key={action.payload}
              onClick={() => sendMessage(action.payload)}
              className="bg-gray-100 hover:bg-gray-200 text-gray-800 px-4 py-2 rounded-full text-sm"
            >
              {action.title}
            </button>
          ))}
        </div>
        <ChatInput onSend={sendMessage} />
      </div>
    </div>
  );
};

export default Chat; 