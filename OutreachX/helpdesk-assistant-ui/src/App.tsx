import React from 'react';
import Layout from './components/Layout';

const App: React.FC = () => {
  const handleTicketCreated = (ticketData: any) => {
    console.log('Ticket created:', ticketData);
    // Handle the created ticket data as needed
  };

  return <Layout onTicketCreated={handleTicketCreated} />;
};

export default App;