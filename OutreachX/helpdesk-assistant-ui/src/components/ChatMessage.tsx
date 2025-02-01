import React from 'react';
import { Message } from '../types/types';

interface ChatMessageProps {
  message: Message;
  onButtonClick: (payload: string) => void;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message, onButtonClick }) => {
  const isBot = message.sender === 'bot';

  const formatMessage = (text: string) => {
    // Replace color markers with styled spans
    return text
      .replace(/\[red\](.*?)\[\/red\]/g, '<span class="text-red-600 font-bold">$1</span>')
      .replace(/\[yellow\](.*?)\[\/yellow\]/g, '<span class="text-yellow-500 font-bold">$1</span>')
      .replace(/\[green\](.*?)\[\/green\]/g, '<span class="text-green-600 font-bold">$1</span>');
  };

  return (
    <div className={`flex ${isBot ? 'justify-start' : 'justify-end'} mb-4`}>
      <div className={`max-w-[70%] rounded-lg p-3 ${
        isBot ? 'bg-gray-200' : 'bg-blue-500 text-white'
      }`}>
        <div 
          dangerouslySetInnerHTML={{ 
            __html: message.text ? formatMessage(message.text) : '' 
          }} 
        />
        {message.buttons && (
          <div className="flex flex-wrap gap-2 mt-2">
            {message.buttons.map((button, index) => (
              <button
                key={`${button.payload}-${index}`}
                onClick={() => onButtonClick(button.payload)}
                className="bg-white text-blue-500 px-3 py-1 rounded-full text-sm"
              >
                {button.title}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage; 