export interface Message {
  id?: string;
  text: string;
  sender: 'user' | 'bot';
  buttons?: Array<{
    title: string;
    payload: string;
  }>;
}

export interface Ticket {
  id: string;
  subject: string;
  status: string;
  createdAt: string;
} 