import { beforeEach, describe, expect, it } from 'vitest'
import { LocalDevStoryIntakeAnalyzer } from '../services/storyIntakeAnalyzer'
import { StoryIntakeService } from '../services/storyIntakeService'
import { storyIntakePersistence } from '../services/storyIntakePersistence'
import { useChatStore } from '@/store/chatStore'

describe('Adaptive Story Intake System', () => {
  let service: StoryIntakeService

  beforeEach(() => {
    window.localStorage.clear()
    storyIntakePersistence.clearAll()
    useChatStore.getState().resetDemoData()
    service = new StoryIntakeService(new LocalDevStoryIntakeAnalyzer())
  })

  it('CASE 1: Nothing provided -> asks Title -> Style -> Context -> awaits confirmation', async () => {
    const convId = 'case_1'
    const projId = 'proj_1'

    const t1 = await service.processUserMessage({
      conversationId: convId,
      projectId: projId,
      message: 'I want to create a story.',
    })
    expect(t1.state.missingFields).toEqual(['story_title', 'visual_style', 'story_context'])
    expect(t1.state.currentQuestion).toBe('story_title')
    expect(t1.assistantContent).toMatch(/title/i)
    expect(t1.showConfirmationCard).toBe(false)

    const t2 = await service.processUserMessage({
      conversationId: convId,
      projectId: projId,
      message: 'The Last Light',
    })
    expect(t2.state.storyTitle.value).toBe('The Last Light')
    expect(t2.state.currentQuestion).toBe('visual_style')
    expect(t2.includeStyleSuggestions).toBe(true)

    const t3 = await service.processUserMessage({
      conversationId: convId,
      projectId: projId,
      message: 'Anime',
    })
    expect(t3.state.visualStyle.value).toBe('Anime')
    expect(t3.state.currentQuestion).toBe('story_context')

    const t4 = await service.processUserMessage({
      conversationId: convId,
      projectId: projId,
      message: 'A girl who can see memories stored inside old photographs.',
    })
    expect(t4.state.status).toBe('awaiting_confirmation')
    expect(t4.showConfirmationCard).toBe(true)
    expect(t4.shouldHandoffToGeneration).toBe(false)
  })

  it('CASE 2: Only title provided -> asks Style -> Context', async () => {
    const t1 = await service.processUserMessage({
      conversationId: 'case_2',
      projectId: 'proj_1',
      message: 'Create a story called The Shadow Within.',
    })
    expect(t1.state.storyTitle.value).toBe('The Shadow Within')
    expect(t1.state.currentQuestion).toBe('visual_style')
    expect(t1.includeStyleSuggestions).toBe(true)
    expect(t1.assistantContent).toMatch(/visual/i)

    const t2 = await service.processUserMessage({
      conversationId: 'case_2',
      projectId: 'proj_1',
      message: 'Cinematic realism',
    })
    expect(t2.state.currentQuestion).toBe('story_context')
    expect(t2.assistantContent).toMatch(/The Shadow Within/)
  })

  it('CASE 3: Only visual style provided -> asks Title -> Context', async () => {
    const t1 = await service.processUserMessage({
      conversationId: 'case_3',
      projectId: 'proj_1',
      message: 'I want a dark fantasy story.',
    })
    expect(t1.state.visualStyle.value).toBe('Dark fantasy')
    expect(t1.state.currentQuestion).toBe('story_title')
    expect(t1.assistantContent).toMatch(/title/i)

    const t2 = await service.processUserMessage({
      conversationId: 'case_3',
      projectId: 'proj_1',
      message: 'Obsidian Crown',
    })
    expect(t2.state.storyTitle.value).toBe('Obsidian Crown')
    expect(t2.state.visualStyle.value).toBe('Dark fantasy')
    // Must skip visual_style and jump directly to story_context
    expect(t2.state.currentQuestion).toBe('story_context')
  })

  it('CASE 4: Only context provided -> asks Title -> Style', async () => {
    const t1 = await service.processUserMessage({
      conversationId: 'case_4',
      projectId: 'proj_1',
      message: 'Create a story about a brother searching for his missing sister.',
    })
    expect(t1.state.storyContext.provided).toBe(true)
    expect(t1.state.storyContext.value).toMatch(/brother searching for his missing sister/i)
    expect(t1.state.currentQuestion).toBe('story_title')

    const t2 = await service.processUserMessage({
      conversationId: 'case_4',
      projectId: 'proj_1',
      message: 'Steps in the Fog',
    })
    expect(t2.state.currentQuestion).toBe('visual_style')
  })

  it('CASE 5: Title and style provided -> asks only for Context', async () => {
    const t1 = await service.processUserMessage({
      conversationId: 'case_5',
      projectId: 'proj_1',
      message: 'Create The Last Light in anime style.',
    })
    expect(t1.state.storyTitle.value).toBe('The Last Light')
    expect(t1.state.visualStyle.value).toBe('Anime')
    expect(t1.state.missingFields).toEqual(['story_context'])
    expect(t1.state.currentQuestion).toBe('story_context')
  })

  it('CASE 6: Title and context provided -> asks only for Style', async () => {
    const t1 = await service.processUserMessage({
      conversationId: 'case_6',
      projectId: 'proj_1',
      message: 'Create The Last Light, a story about a girl saving her village.',
    })
    expect(t1.state.storyTitle.value).toBe('The Last Light')
    expect(t1.state.storyContext.value).toMatch(/girl saving her village/i)
    expect(t1.state.missingFields).toEqual(['visual_style'])
    expect(t1.state.currentQuestion).toBe('visual_style')
    expect(t1.includeStyleSuggestions).toBe(true)
  })

  it('CASE 7: Style and context provided -> asks only for Title', async () => {
    const t1 = await service.processUserMessage({
      conversationId: 'case_7',
      projectId: 'proj_1',
      message: 'Create a dark fantasy story about a kingdom that has lost its sun.',
    })
    expect(t1.state.visualStyle.value).toBe('Dark fantasy')
    expect(t1.state.storyContext.value).toMatch(/kingdom that has lost its sun/i)
    expect(t1.state.missingFields).toEqual(['story_title'])
    expect(t1.state.currentQuestion).toBe('story_title')
  })

  it('CASE 8: All three fields provided in one message -> moves straight to confirmation without generating', async () => {
    const t1 = await service.processUserMessage({
      conversationId: 'case_8',
      projectId: 'proj_1',
      message:
        'Create The Last Light, a dark fantasy story about a girl trying to save her village after the sun disappears.',
    })
    expect(t1.state.storyTitle.value).toBe('The Last Light')
    expect(t1.state.visualStyle.value).toBe('Dark fantasy')
    expect(t1.state.storyContext.value).toMatch(/girl trying to save her village/i)
    expect(t1.state.missingFields).toEqual([])
    expect(t1.state.status).toBe('awaiting_confirmation')
    expect(t1.showConfirmationCard).toBe(true)
    expect(t1.shouldHandoffToGeneration).toBe(false)
  })

  it('understands rich natural-language visual styles and story context metadata', async () => {
    await service.processUserMessage({
      conversationId: 'nl_1',
      projectId: 'proj_1',
      message: 'Create a story called Blue Lantern.',
    })

    const styleTurn = await service.processUserMessage({
      conversationId: 'nl_1',
      projectId: 'proj_1',
      message:
        'I want a story that looks like a dark, mysterious animated film with deep blue lighting.',
    })
    expect(styleTurn.state.visualStyle.provided).toBe(true)
    expect(styleTurn.state.visualStyle.details?.medium).toBe('Animation')
    expect(styleTurn.state.visualStyle.details?.lighting).toMatch(/deep blue/i)
    expect(styleTurn.state.currentQuestion).toBe('story_context')

    const ctxTurn = await service.processUserMessage({
      conversationId: 'nl_1',
      projectId: 'proj_1',
      message:
        "It's about how people lose trust when they repeatedly lie, and how one person tries to rebuild it.",
    })
    expect(ctxTurn.state.storyContext.provided).toBe(true)
    expect(ctxTurn.state.storyContext.theme).toBe('Trust')
    expect(ctxTurn.state.storyContext.mainConflict).toMatch(/dishonesty/i)
    expect(ctxTurn.state.status).toBe('awaiting_confirmation')
  })

  it('supports modifying title, modifying visual style, and adding context while preserving other fields', async () => {
    await service.processUserMessage({
      conversationId: 'mod_1',
      projectId: 'proj_1',
      message:
        'Create The Last Light, an anime story about a girl trying to save her village.',
    })

    const modStyle = await service.processUserMessage({
      conversationId: 'mod_1',
      projectId: 'proj_1',
      message: 'Actually, change the style to cinematic realism.',
    })
    expect(modStyle.state.visualStyle.value).toBe('Cinematic realism')
    expect(modStyle.state.storyTitle.value).toBe('The Last Light')
    expect(modStyle.state.storyContext.value).toMatch(/girl trying to save her village/i)
    expect(modStyle.assistantContent).toMatch(/updated the visual style/i)

    const modTitle = await service.processUserMessage({
      conversationId: 'mod_1',
      projectId: 'proj_1',
      message: 'Change the title to The Forgotten Light.',
    })
    expect(modTitle.state.storyTitle.value).toBe('The Forgotten Light')
    expect(modTitle.state.visualStyle.value).toBe('Cinematic realism')
    expect(modTitle.assistantContent).toMatch(/updated the story title/i)

    const addCtx = await service.processUserMessage({
      conversationId: 'mod_1',
      projectId: 'proj_1',
      message: 'Also, she discovers an ancient compass hidden beneath the bell tower.',
    })
    expect(addCtx.state.storyContext.value).toMatch(/girl trying to save her village/i)
    expect(addCtx.state.storyContext.value).toMatch(/ancient compass/i)
  })

  it('handles ambiguous answers, title suggestions, and unrelated questions without losing intake state', async () => {
    await service.processUserMessage({
      conversationId: 'edge_1',
      projectId: 'proj_1',
      message: 'I want an anime story about a girl who can see memories.',
    })

    // Unrelated question during pending title question
    const unrelated = await service.processUserMessage({
      conversationId: 'edge_1',
      projectId: 'proj_1',
      message: 'What can StoryForge do?',
    })
    expect(unrelated.state.visualStyle.value).toBe('Anime')
    expect(unrelated.state.storyContext.provided).toBe(true)
    expect(unrelated.state.currentQuestion).toBe('story_title')
    expect(unrelated.assistantContent).toMatch(/StoryForge helps/i)

    // Suggest title request should offer suggestions, never invent silently
    const suggest = await service.processUserMessage({
      conversationId: 'edge_1',
      projectId: 'proj_1',
      message: 'Can you suggest a title?',
    })
    expect(suggest.state.storyTitle.provided).toBe(false)
    expect(suggest.titleOptions?.length).toBeGreaterThanOrEqual(3)

    // Select a suggested title -> reaches confirmation
    const picked = await service.processUserMessage({
      conversationId: 'edge_1',
      projectId: 'proj_1',
      message: suggest.titleOptions![0],
    })
    expect(picked.state.storyTitle.value).toBe(suggest.titleOptions![0])
    expect(picked.state.status).toBe('awaiting_confirmation')

    // Ambiguous answer check
    await service.processUserMessage({
      conversationId: 'edge_2',
      projectId: 'proj_1',
      message: 'Create Silver Gate in anime style.',
    })
    const vague = await service.processUserMessage({
      conversationId: 'edge_2',
      projectId: 'proj_1',
      message: 'something cool',
    })
    expect(vague.state.storyContext.provided).toBe(false)
    expect(vague.assistantContent).toMatch(/more detail/i)
  })

  it('persists and restores per-conversation intake state across conversation switches and requires explicit confirmation', async () => {
    const store = useChatStore.getState()

    // Start conversation A (only style + context)
    const convA = await store.sendMessage(
      'I want an anime story about a girl who can see people’s memories.'
    )
    // Start conversation B (new chat, only title)
    store.createNewChat()
    const convB = await store.sendMessage('Create a story called Harbor of Echoes.')

    // Switch back to conversation A and verify its intake state is intact
    store.setActiveConversation(convA)
    const stateA = storyIntakePersistence.get(convA)
    expect(stateA?.visualStyle.value).toBe('Anime')
    expect(stateA?.storyTitle.provided).toBe(false)
    expect(stateA?.currentQuestion).toBe('story_title')

    // Supply title to A -> should enter awaiting_confirmation (not confirmed yet)
    await store.sendMessage('The Memory Glass', undefined, convA)
    const convAAfterTitle = useChatStore
      .getState()
      .conversations.find((c) => c.id === convA)
    expect(convAAfterTitle?.intakeState?.status).toBe('awaiting_confirmation')
    expect(convAAfterTitle?.intakeState?.storyTitle.confirmed).toBe(false)

    // Confirm explicitly via confirmation card action
    const confirmMsg = convAAfterTitle!.messages[convAAfterTitle!.messages.length - 1]
    await useChatStore.getState().confirmStoryIntake(convA, confirmMsg.id)

    const convAConfirmed = useChatStore
      .getState()
      .conversations.find((c) => c.id === convA)
    expect(convAConfirmed?.intakeState?.status).toBe('completed')
    expect(convAConfirmed?.intakeState?.storyTitle.confirmed).toBe(true)

    // Verify conversation B remains unaffected in collecting state
    const stateB = storyIntakePersistence.get(convB)
    expect(stateB?.storyTitle.value).toBe('Harbor of Echoes')
    expect(stateB?.status).toBe('collecting')
  })
})
