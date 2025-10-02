import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import BackRoomView from '../BackRoomView';
import { ChatRoom, BackRoom, Message, User } from '@/lib/api';
import * as api from '@/lib/api';

// Mock ChatMessage component that doesn't exist yet
jest.mock('../ChatMessage', () => {
  return function MockChatMessage() {
    return <div data-testid="chat-message">Message</div>;
  };
});

// Mock the API
jest.mock('@/lib/api', () => ({
  ...jest.requireActual('@/lib/api'),
  backRoomApi: {
    getMessages: jest.fn(),
    sendMessage: jest.fn(),
    joinBackRoom: jest.fn(),
  },
}));

describe('BackRoomView', () => {
  const mockHost: User = {
    id: 'host-1',
    email: 'host@test.com',
    display_name: 'Host User',
    first_name: 'Host',
    last_name: 'User',
    email_notifications: true,
    push_notifications: true,
    subscriber_count: 0,
    subscription_count: 0,
    created_at: '2025-01-01T00:00:00Z',
    last_active: '2025-01-01T00:00:00Z',
  };

  const mockChatRoom: ChatRoom = {
    id: 'chat-1',
    code: 'ABC123',
    name: 'Test Chat',
    description: 'Test Description',
    host: mockHost,
    url: 'http://test.com/ABC123',
    access_mode: 'public',
    voice_enabled: false,
    video_enabled: false,
    photo_enabled: false,
    message_count: 0,
    has_back_room: true,
    is_active: true,
    created_at: '2025-01-01T00:00:00Z',
  };

  const mockBackRoom: BackRoom = {
    id: 'backroom-1',
    chat_room: 'chat-1',
    price_per_seat: '10.00',
    max_seats: 5,
    seats_occupied: 2,
    seats_available: 3,
    is_full: false,
    is_active: true,
    created_at: '2025-01-01T00:00:00Z',
  };

  const mockMessages: Message[] = [
    {
      id: 'msg-1',
      chat_room: 'chat-1',
      username: 'TestUser',
      user: null,
      message_type: 'normal',
      content: 'Test message 1',
      reply_to: null,
      reply_to_message: null,
      is_pinned: false,
      pinned_at: null,
      pinned_until: null,
      pin_amount_paid: '0',
      is_from_host: false,
      time_until_unpin: null,
      created_at: '2025-01-01T00:00:00Z',
      is_deleted: false,
    },
    {
      id: 'msg-2',
      chat_room: 'chat-1',
      username: 'Host User',
      user: mockHost,
      message_type: 'host',
      content: 'Test message 2',
      reply_to: null,
      reply_to_message: null,
      is_pinned: false,
      pinned_at: null,
      pinned_until: null,
      pin_amount_paid: '0',
      is_from_host: true,
      time_until_unpin: null,
      created_at: '2025-01-01T00:00:00Z',
      is_deleted: false,
    },
  ];

  const mockOnBack = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    (api.backRoomApi.getMessages as jest.Mock).mockResolvedValue(mockMessages);
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  it('should render header with seats available', () => {
    render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="TestUser"
        currentUserId="user-1"
        isMember={true}
        onBack={mockOnBack}
      />
    );
    expect(screen.getByText('Back Room')).toBeInTheDocument();
    expect(screen.getByText('3 seats left')).toBeInTheDocument();
  });

  it('should load messages for members', async () => {
    render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="TestUser"
        currentUserId="user-1"
        isMember={true}
        onBack={mockOnBack}
      />
    );

    await waitFor(() => {
      expect(api.backRoomApi.getMessages).toHaveBeenCalledWith('ABC123', 'TestUser');
    });
  });

  it('should load messages for host', async () => {
    render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="Host User"
        currentUserId="host-1"
        isMember={false}
        onBack={mockOnBack}
      />
    );

    await waitFor(() => {
      expect(api.backRoomApi.getMessages).toHaveBeenCalledWith('ABC123', 'Host User');
    });
  });

  it('should not load messages for non-members', () => {
    render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="NonMember"
        currentUserId="user-2"
        isMember={false}
        onBack={mockOnBack}
      />
    );

    expect(api.backRoomApi.getMessages).not.toHaveBeenCalled();
  });

  it('should show blurred messages for non-members', () => {
    const { container } = render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="NonMember"
        currentUserId="user-2"
        isMember={false}
        onBack={mockOnBack}
      />
    );

    const messagesContainer = container.querySelector('.blur-md');
    expect(messagesContainer).toBeInTheDocument();
  });

  it('should show join overlay for non-members', () => {
    render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="NonMember"
        currentUserId="user-2"
        isMember={false}
        onBack={mockOnBack}
      />
    );

    expect(screen.getByText(`Join Back Room - $${mockBackRoom.price_per_seat}`)).toBeInTheDocument();
  });

  it('should not show join overlay for members', async () => {
    render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="TestUser"
        currentUserId="user-1"
        isMember={true}
        onBack={mockOnBack}
      />
    );

    await waitFor(() => {
      expect(screen.queryByText(`Join Back Room - $${mockBackRoom.price_per_seat}`)).not.toBeInTheDocument();
    });
  });

  it('should show message input for members', async () => {
    render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="TestUser"
        currentUserId="user-1"
        isMember={true}
        onBack={mockOnBack}
      />
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
    });
  });

  it('should not show message input for non-members', () => {
    render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="NonMember"
        currentUserId="user-2"
        isMember={false}
        onBack={mockOnBack}
      />
    );

    expect(screen.queryByPlaceholderText('Type your message...')).not.toBeInTheDocument();
  });

  it('should send message when form is submitted', async () => {
    (api.backRoomApi.sendMessage as jest.Mock).mockResolvedValue({});

    render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="TestUser"
        currentUserId="user-1"
        isMember={true}
        onBack={mockOnBack}
      />
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Type your message...');
    const sendButton = screen.getByText('Send');

    fireEvent.change(input, { target: { value: 'New test message' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(api.backRoomApi.sendMessage).toHaveBeenCalledWith('ABC123', 'TestUser', 'New test message');
    });
  });

  it('should not send empty messages', async () => {
    render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="TestUser"
        currentUserId="user-1"
        isMember={true}
        onBack={mockOnBack}
      />
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
    });

    const sendButton = screen.getByText('Send');
    expect(sendButton).toBeDisabled();
  });

  it('should clear input after sending message', async () => {
    (api.backRoomApi.sendMessage as jest.Mock).mockResolvedValue({});

    render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="TestUser"
        currentUserId="user-1"
        isMember={true}
        onBack={mockOnBack}
      />
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Type your message...') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => {
      expect(input.value).toBe('');
    });
  });

  it('should poll for messages every 3 seconds', async () => {
    render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="TestUser"
        currentUserId="user-1"
        isMember={true}
        onBack={mockOnBack}
      />
    );

    // Initial load
    await waitFor(() => {
      expect(api.backRoomApi.getMessages).toHaveBeenCalledTimes(1);
    });

    // Advance 3 seconds
    jest.advanceTimersByTime(3000);
    await waitFor(() => {
      expect(api.backRoomApi.getMessages).toHaveBeenCalledTimes(2);
    });

    // Advance another 3 seconds
    jest.advanceTimersByTime(3000);
    await waitFor(() => {
      expect(api.backRoomApi.getMessages).toHaveBeenCalledTimes(3);
    });
  });

  it('should open join modal when join button is clicked', () => {
    render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="NonMember"
        currentUserId="user-2"
        isMember={false}
        onBack={mockOnBack}
      />
    );

    const joinButton = screen.getByText(`Join Back Room - $${mockBackRoom.price_per_seat}`);
    fireEvent.click(joinButton);

    expect(screen.getByText('Join Back Room')).toBeInTheDocument();
  });

  it('should handle message load errors gracefully', async () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();
    (api.backRoomApi.getMessages as jest.Mock).mockRejectedValue(new Error('Failed to load'));

    render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="TestUser"
        currentUserId="user-1"
        isMember={true}
        onBack={mockOnBack}
      />
    );

    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Failed to load back room messages:',
        expect.any(Error)
      );
    });

    consoleErrorSpy.mockRestore();
  });

  it('should disable send button while loading', async () => {
    (api.backRoomApi.sendMessage as jest.Mock).mockImplementation(
      () => new Promise(resolve => setTimeout(resolve, 100))
    );

    render(
      <BackRoomView
        chatRoom={mockChatRoom}
        backRoom={mockBackRoom}
        username="TestUser"
        currentUserId="user-1"
        isMember={true}
        onBack={mockOnBack}
      />
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Type your message...');
    const sendButton = screen.getByText('Send');

    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.click(sendButton);

    expect(sendButton).toBeDisabled();
  });
});
