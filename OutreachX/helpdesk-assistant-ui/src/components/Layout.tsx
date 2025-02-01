import React, { useState } from 'react';
import Chat from './Chat';
import TicketsSidebar from './TicketsSidebar';
import './Layout.css';

interface LayoutProps {
  onTicketCreated: (ticketData: any) => void; // Define the type as needed
}

const Layout: React.FC<LayoutProps> = ({ onTicketCreated }) => {
  const [userEmail, setUserEmail] = useState<string>('user@example.com'); // Added userEmail state

  const handleTicketClick = (ticketId: string) => {
    console.log('Ticket clicked:', ticketId);
  };

  return (
    <div className="layout-container">
      <div className='sidebar'>
      <TicketsSidebar 
        userEmail={userEmail}
        onTicketClick={handleTicketClick} 
      />
      </div>
      <div className="chat-section">
        <Chat onTicketCreated={onTicketCreated} />
      </div>
    </div>
  );
};

export default Layout;
