import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import BackRoomJoinModal from '../BackRoomJoinModal';
import { BackRoom } from '@/lib/api';

describe('BackRoomJoinModal', () => {
  const mockBackRoom: BackRoom = {
    id: '1',
    chat_room: 'chat-1',
    price_per_seat: '10.00',
    max_seats: 5,
    seats_occupied: 2,
    seats_available: 3,
    is_full: false,
    is_active: true,
    created_at: '2025-01-01T00:00:00Z',
  };

  const mockOnJoin = jest.fn();
  const mockOnClose = jest.fn();

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should render with back room details', () => {
    render(
      <BackRoomJoinModal
        backRoom={mockBackRoom}
        onJoin={mockOnJoin}
        onClose={mockOnClose}
      />
    );
    expect(screen.getByText('Join Back Room')).toBeInTheDocument();
    expect(screen.getByText('$10.00')).toBeInTheDocument();
    expect(screen.getByText('3 / 5')).toBeInTheDocument();
  });

  it('should call onClose when backdrop is clicked', () => {
    const { container } = render(
      <BackRoomJoinModal
        backRoom={mockBackRoom}
        onJoin={mockOnJoin}
        onClose={mockOnClose}
      />
    );
    const backdrop = container.querySelector('.bg-black\\/60');
    if (backdrop) {
      fireEvent.click(backdrop);
    }
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('should call onClose when close button is clicked', () => {
    render(
      <BackRoomJoinModal
        backRoom={mockBackRoom}
        onJoin={mockOnJoin}
        onClose={mockOnClose}
      />
    );
    const closeButtons = screen.getAllByRole('button');
    // Find the X button (first button in the modal)
    const xButton = closeButtons[0];
    fireEvent.click(xButton);
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('should call onClose when Cancel button is clicked', () => {
    render(
      <BackRoomJoinModal
        backRoom={mockBackRoom}
        onJoin={mockOnJoin}
        onClose={mockOnClose}
      />
    );
    const cancelButton = screen.getByText('Cancel');
    fireEvent.click(cancelButton);
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('should call onJoin when join button is clicked', async () => {
    mockOnJoin.mockResolvedValue(undefined);
    render(
      <BackRoomJoinModal
        backRoom={mockBackRoom}
        onJoin={mockOnJoin}
        onClose={mockOnClose}
      />
    );
    const joinButton = screen.getByText(`Join - $${mockBackRoom.price_per_seat}`);
    fireEvent.click(joinButton);

    await waitFor(() => {
      expect(mockOnJoin).toHaveBeenCalledTimes(1);
    });
  });

  it('should show loading state when joining', async () => {
    mockOnJoin.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 100)));
    render(
      <BackRoomJoinModal
        backRoom={mockBackRoom}
        onJoin={mockOnJoin}
        onClose={mockOnClose}
      />
    );
    const joinButton = screen.getByText(`Join - $${mockBackRoom.price_per_seat}`);
    fireEvent.click(joinButton);

    expect(await screen.findByText('Joining...')).toBeInTheDocument();
  });

  it('should disable join button when loading', async () => {
    mockOnJoin.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 100)));
    render(
      <BackRoomJoinModal
        backRoom={mockBackRoom}
        onJoin={mockOnJoin}
        onClose={mockOnClose}
      />
    );
    const joinButton = screen.getByText(`Join - $${mockBackRoom.price_per_seat}`);
    fireEvent.click(joinButton);

    await waitFor(() => {
      expect(joinButton).toBeDisabled();
    });
  });

  it('should show "Full" when back room is full', () => {
    const fullBackRoom = { ...mockBackRoom, is_full: true };
    render(
      <BackRoomJoinModal
        backRoom={fullBackRoom}
        onJoin={mockOnJoin}
        onClose={mockOnClose}
      />
    );
    expect(screen.getByText('Full')).toBeInTheDocument();
  });

  it('should disable join button when back room is full', () => {
    const fullBackRoom = { ...mockBackRoom, is_full: true };
    render(
      <BackRoomJoinModal
        backRoom={fullBackRoom}
        onJoin={mockOnJoin}
        onClose={mockOnClose}
      />
    );
    const joinButton = screen.getByText('Full');
    expect(joinButton).toBeDisabled();
  });

  it('should display price per seat info', () => {
    render(
      <BackRoomJoinModal
        backRoom={mockBackRoom}
        onJoin={mockOnJoin}
        onClose={mockOnClose}
      />
    );
    expect(screen.getByText('Price per seat')).toBeInTheDocument();
    expect(screen.getByText('Seats available')).toBeInTheDocument();
  });

  it('should handle join error gracefully', async () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();
    mockOnJoin.mockRejectedValue(new Error('Join failed'));

    render(
      <BackRoomJoinModal
        backRoom={mockBackRoom}
        onJoin={mockOnJoin}
        onClose={mockOnClose}
      />
    );
    const joinButton = screen.getByText(`Join - $${mockBackRoom.price_per_seat}`);
    fireEvent.click(joinButton);

    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Failed to join back room:',
        expect.any(Error)
      );
    });

    consoleErrorSpy.mockRestore();
  });

  it('should render modal with correct structure', () => {
    const { container } = render(
      <BackRoomJoinModal
        backRoom={mockBackRoom}
        onJoin={mockOnJoin}
        onClose={mockOnClose}
      />
    );

    // Check for modal overlay
    expect(container.querySelector('.fixed.inset-0.z-50')).toBeInTheDocument();

    // Check for backdrop
    expect(container.querySelector('.bg-black\\/60.backdrop-blur-sm')).toBeInTheDocument();

    // Check for modal content
    expect(container.querySelector('.bg-white.dark\\:bg-gray-900.rounded-2xl')).toBeInTheDocument();
  });
});
