import React, { useEffect, useState } from "react";

interface Ticket {
  PartitionKey: string;
  Title: string;
  Priority: string;
  Description: string;
  CreatedDate: string;
  MessageUrl?: string; // Add a field for the Outlook URL
}

interface TicketsSidebarProps {
  userEmail: string;
  onTicketClick: (ticketId: string) => void;
}

const TicketsSidebar: React.FC<TicketsSidebarProps> = ({
  userEmail,
  onTicketClick,
}) => {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchTickets = async () => {
      try {
        setLoading(true); // Start loading
        console.log(`Fetching tickets for email: ${userEmail}`);

        const response = await fetch("http://localhost:5055/webhook", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            next_action: "action_fetch_user_tickets",
            tracker: {
              sender_id: "demo",
              conversation_id: "default",
              slots: {
                email: userEmail,
              },
            },
          }),
        });

        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();
        console.log("Tickets response:", data);

        // Safely extract and parse tickets
        const parsedTickets =
          data.responses?.[0]?.custom?.tickets || [];

        // Add messageUrl to each ticket if available
        const updatedTickets = parsedTickets.map((ticket: any) => ({
          ...ticket,
          MessageUrl: ticket.MessageUrl || null, // If the backend provides messageUrl
        }));

        setTickets(updatedTickets); // Update tickets
      } catch (error: any) {
        console.error("Fetch error:", error);
        setError(error.message || "An unknown error occurred while fetching tickets.");
      } finally {
        setLoading(false); // End loading
      }
    };

    if (userEmail) {
      fetchTickets();
    }
  }, [userEmail]);

  if (loading) {
    return <div>Loading tickets...</div>;
  }

  if (error) {
    return <div>Error fetching tickets: {error}</div>;
  }

  return (
    <div
      className="fixed h-full bg-white p-4 border-r border-gray-200 overflow-y-auto"
      style={{ width: "250px" }} // Fixed width for the left pane
    >
      <h2 className="text-lg font-semibold mb-4">Your Tickets</h2>
      <div className="space-y-2">
        {tickets.map((ticket) => (
          <div
            key={ticket.PartitionKey}
            onClick={() => onTicketClick(ticket.PartitionKey)}
            className="p-3 bg-gray-100 rounded-lg shadow-sm cursor-pointer hover:bg-gray-200"
          >
            <h3 className="text-sm font-medium">{ticket.PartitionKey}</h3>
            <h4 className="text-sm font-medium">{ticket.Title}</h4>
            <p className="text-xs text-gray-600 truncate">
              {ticket.Description || "No description available"}
            </p>
            <p className="text-xs text-gray-600">
              Priority: {ticket.Priority || "Not set"}
            </p>
            <p className="text-xs text-gray-500">
              Created: {new Date(ticket.CreatedDate).toLocaleString()}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default TicketsSidebar;
