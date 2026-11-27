import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { StoryConfirmation } from '../components/StoryConfirmation'
import type { StoryIntakeState } from '../types/storyIntake.types'

const sampleIntake: StoryIntakeState = {
  projectId: 'proj_1',
  conversationId: 'conv_1',
  storyTitle: { value: 'The Last Light', provided: true, confirmed: false },
  visualStyle: { value: 'Dark fantasy animation', provided: true, confirmed: false },
  storyContext: {
    value: 'A young girl attempts to save her village after the sun mysteriously disappears.',
    provided: true,
    confirmed: false,
  },
  missingFields: [],
  currentQuestion: null,
  status: 'awaiting_confirmation',
  awaitingConfirmation: true,
  generationStarted: false,
  updatedAt: Date.now(),
}

describe('StoryConfirmation', () => {
  it('renders summary and handles Confirm and develop + Edit details actions', () => {
    const onConfirm = vi.fn()
    const onEdit = vi.fn()

    render(
      <StoryConfirmation
        intake={sampleIntake}
        onConfirm={onConfirm}
        onEdit={onEdit}
      />
    )

    expect(screen.getByText('The Last Light')).toBeInTheDocument()
    expect(screen.getByText('Dark fantasy animation')).toBeInTheDocument()
    expect(
      screen.getByText(/A young girl attempts to save her village/i)
    ).toBeInTheDocument()

    // Click Edit details -> reveals per-field edit buttons
    fireEvent.click(screen.getByRole('button', { name: /Edit details/i }))
    fireEvent.click(screen.getByRole('button', { name: /Edit Visual Style/i }))
    expect(onEdit).toHaveBeenCalledWith('visual_style')

    // Click Confirm and develop
    fireEvent.click(screen.getByRole('button', { name: /Confirm and develop/i }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('displays confirmed badge and hides confirmation buttons once confirmed', () => {
    render(
      <StoryConfirmation
        intake={{ ...sampleIntake, status: 'completed' }}
        decision="confirmed"
        onConfirm={vi.fn()}
        onEdit={vi.fn()}
      />
    )

    expect(screen.getByText('Confirmed')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Confirm and develop/i })
    ).not.toBeInTheDocument()
  })
})
