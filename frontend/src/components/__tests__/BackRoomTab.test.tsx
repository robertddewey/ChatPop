import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import BackRoomTab from '../BackRoomTab';

describe('BackRoomTab', () => {
  const mockOnClick = jest.fn();

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should not render when hasBackRoom is false', () => {
    const { container } = render(
      <BackRoomTab
        isInBackRoom={false}
        hasBackRoom={false}
        onClick={mockOnClick}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('should render with "Back Room" label when in main chat', () => {
    render(
      <BackRoomTab
        isInBackRoom={false}
        hasBackRoom={true}
        onClick={mockOnClick}
      />
    );
    expect(screen.getByText('Back Room')).toBeInTheDocument();
  });

  it('should render with "Main Chat" label when in back room', () => {
    render(
      <BackRoomTab
        isInBackRoom={true}
        hasBackRoom={true}
        onClick={mockOnClick}
      />
    );
    expect(screen.getByText('Main Chat')).toBeInTheDocument();
  });

  it('should call onClick when clicked', () => {
    render(
      <BackRoomTab
        isInBackRoom={false}
        hasBackRoom={true}
        onClick={mockOnClick}
      />
    );
    const button = screen.getByRole('button');
    fireEvent.click(button);
    expect(mockOnClick).toHaveBeenCalledTimes(1);
  });

  it('should have purple background when in main chat', () => {
    render(
      <BackRoomTab
        isInBackRoom={false}
        hasBackRoom={true}
        onClick={mockOnClick}
      />
    );
    const button = screen.getByRole('button');
    expect(button).toHaveClass('bg-purple-600');
  });

  it('should have gray background when in back room', () => {
    render(
      <BackRoomTab
        isInBackRoom={true}
        hasBackRoom={true}
        onClick={mockOnClick}
      />
    );
    const button = screen.getByRole('button');
    expect(button).toHaveClass('bg-gray-800');
  });

  it('should show notification badge when hasNewMessages is true and in main chat', () => {
    const { container } = render(
      <BackRoomTab
        isInBackRoom={false}
        hasBackRoom={true}
        onClick={mockOnClick}
        hasNewMessages={true}
      />
    );
    const badge = container.querySelector('.bg-red-500');
    expect(badge).toBeInTheDocument();
  });

  it('should not show notification badge when in back room', () => {
    const { container } = render(
      <BackRoomTab
        isInBackRoom={true}
        hasBackRoom={true}
        onClick={mockOnClick}
        hasNewMessages={true}
      />
    );
    const badge = container.querySelector('.bg-red-500');
    expect(badge).not.toBeInTheDocument();
  });

  it('should have animate-pulse class when hasNewMessages and in main chat', () => {
    render(
      <BackRoomTab
        isInBackRoom={false}
        hasBackRoom={true}
        onClick={mockOnClick}
        hasNewMessages={true}
      />
    );
    const button = screen.getByRole('button');
    expect(button).toHaveClass('animate-pulse');
  });

  it('should have correct aria-label when in main chat', () => {
    render(
      <BackRoomTab
        isInBackRoom={false}
        hasBackRoom={true}
        onClick={mockOnClick}
      />
    );
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-label', 'Open Back Room');
  });

  it('should have correct aria-label when in back room', () => {
    render(
      <BackRoomTab
        isInBackRoom={true}
        hasBackRoom={true}
        onClick={mockOnClick}
      />
    );
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-label', 'Return to Main Chat');
  });
});
