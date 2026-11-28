import jsPDF from 'jspdf'
import autoTable, { type CellHookData, type UserOptions } from 'jspdf-autotable'
import type { Shot, ShotPlanner } from '@/types/planner'

/**
 * Client-side Shot Planner PDF generator matching the approved reference layout
 * ("PRODUCTION SHOT PLANNER (1 SHOT = 1 FRAME)").
 *
 * Page 1: film title, logline, statistics band, creator's intent, shot rule, characters, locations.
 * Following pages: one section per scene with a 10-column shot table. Every row is ONE camera
 * setup (one framing + one angle); a change of angle or framing is always a new shot row.
 */

type RGB = [number, number, number]

const ACCENT: RGB = [192, 80, 42]
const TEXT_DARK: RGB = [40, 40, 46]
const TEXT_BODY: RGB = [60, 60, 66]
const TEXT_MUTED: RGB = [110, 110, 116]
const HEADER_DARK: RGB = [44, 44, 52]
const ROW_ALT: RGB = [245, 241, 234]
const STATS_BG: RGB = [243, 239, 232]
const BORDER: RGB = [222, 216, 206]

const MARGIN = 40
const FOOTER_GAP = 22

export const SHOT_RULE_TEXT =
  'Every shot is one frame: one subject, one action, one camera setup, one location and one moment. ' +
  'Whenever the subject, action, angle, location, lighting, insert detail or reaction changes, a new shot ' +
  'begins. Each shot runs 5 seconds or less, except deeply emotional dialogue (up to 7 seconds).'

function lastY(doc: jsPDF): number {
  return (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY
}

function sectionHeading(doc: jsPDF, label: string, y: number): number {
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(9.5)
  doc.setTextColor(...ACCENT)
  doc.text(label.toUpperCase(), MARGIN, y)
  return y + 12
}

function paragraph(doc: jsPDF, text: string, y: number, width: number): number {
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9.5)
  doc.setTextColor(...TEXT_BODY)
  const lines = doc.splitTextToSize(text || '—', width)
  doc.text(lines, MARGIN, y)
  return y + lines.length * 12.5 + 10
}

function baseTableOptions(): Partial<UserOptions> {
  return {
    margin: { left: MARGIN, right: MARGIN, bottom: MARGIN + FOOTER_GAP },
    theme: 'grid',
    headStyles: {
      fillColor: HEADER_DARK,
      textColor: [255, 255, 255],
      fontStyle: 'bold',
      fontSize: 8,
      cellPadding: 5,
      lineColor: HEADER_DARK,
    },
    bodyStyles: {
      textColor: TEXT_BODY,
      fontSize: 7.8,
      cellPadding: 5,
      valign: 'top',
      lineColor: BORDER,
      lineWidth: 0.5,
    },
    alternateRowStyles: { fillColor: ROW_ALT },
    columnStyles: { 0: { fontStyle: 'bold', textColor: TEXT_DARK } },
  }
}

function formatDialogue(shot: Shot): string {
  const d = shot.dialogue
  if (!d || !d.line?.trim()) return 'None'
  const delivery = d.delivery?.trim() ? ` (${d.delivery.trim()})` : ''
  return `${d.speaker}: “${d.line.trim()}”${delivery}`
}

function drawFooters(doc: jsPDF, filmTitle: string): void {
  const pageCount = doc.getNumberOfPages()
  const pageWidth = doc.internal.pageSize.getWidth()
  const pageHeight = doc.internal.pageSize.getHeight()
  const label = `${filmTitle.toUpperCase()} • PRODUCTION SHOT PLANNER (1 SHOT = 1 FRAME)`
  for (let i = 1; i <= pageCount; i += 1) {
    doc.setPage(i)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7.5)
    doc.setTextColor(...TEXT_MUTED)
    doc.text(label, MARGIN, pageHeight - MARGIN + 12)
    doc.text(`Page ${i}`, pageWidth - MARGIN, pageHeight - MARGIN + 12, { align: 'right' })
  }
}

export function buildShotPlannerPdf(planner: ShotPlanner): jsPDF {
  const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' })
  const pageWidth = doc.internal.pageSize.getWidth()
  const contentWidth = pageWidth - MARGIN * 2
  const { overview } = planner
  const filmTitle = overview.filmTitle || 'Untitled Story'

  // Totals are always derived from the actual shot rows so the header never disagrees with the tables.
  const allShots = planner.scenes.flatMap((s) => s.shots)
  const totalShots = allShots.length
  const dialogueLines = allShots.filter((s) => s.dialogue && s.dialogue.line?.trim()).length
  const runningTime = allShots.reduce((sum, s) => sum + (Number(s.durationSeconds) || 0), 0)

  // ------------------------------------------------------------------ Page 1: overview
  let y = 52
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(8.5)
  doc.setTextColor(...ACCENT)
  doc.text('STORYFORGE • PRODUCTION SHOT PLANNER', MARGIN, y)

  y += 28
  doc.setFontSize(26)
  doc.setTextColor(...TEXT_DARK)
  doc.text(filmTitle, MARGIN, y)

  y += 18
  y = paragraph(doc, overview.logline, y, contentWidth) - 2

  autoTable(doc, {
    startY: y,
    margin: { left: MARGIN, right: MARGIN },
    theme: 'plain',
    tableLineColor: BORDER,
    tableLineWidth: 0.6,
    styles: { fillColor: STATS_BG, textColor: TEXT_DARK, cellPadding: { top: 7, bottom: 5, left: 10, right: 10 } },
    headStyles: { fontStyle: 'bold', fontSize: 7.5, textColor: TEXT_BODY },
    bodyStyles: { fontStyle: 'bold', fontSize: 15, cellPadding: { top: 2, bottom: 8, left: 10, right: 10 } },
    head: [['Scenes', 'Total Shots', 'Dialogue Lines', 'Running Time', 'Video Format', 'Frame Rate']],
    body: [
      [
        String(planner.scenes.length),
        String(totalShots),
        String(dialogueLines),
        `${runningTime}s`,
        overview.videoFormat || '16:9 HD',
        overview.frameRate || '24fps',
      ],
    ],
  })

  y = lastY(doc) + 20
  y = sectionHeading(doc, "Creator's Intent", y)
  y = paragraph(doc, overview.creatorsIntent, y, contentWidth)

  y = sectionHeading(doc, 'Shot Rule Applied', y)
  y = paragraph(doc, SHOT_RULE_TEXT, y, contentWidth)

  y = sectionHeading(doc, 'Characters', y)
  autoTable(doc, {
    ...baseTableOptions(),
    startY: y - 4,
    columnStyles: {
      0: { cellWidth: 100, fontStyle: 'bold', textColor: TEXT_DARK },
      1: { cellWidth: 160 },
      2: { cellWidth: (contentWidth - 260) / 2 },
      3: { cellWidth: (contentWidth - 260) / 2 },
    },
    head: [['Name', 'Role', 'Physical Appearance', 'Personality & Voice']],
    body: planner.characters.map((c) => [c.name, c.role, c.physicalAppearance, c.personalityAndVoice]),
  })

  y = lastY(doc) + 20
  y = sectionHeading(doc, 'Locations', y)
  autoTable(doc, {
    ...baseTableOptions(),
    startY: y - 4,
    columnStyles: {
      0: { cellWidth: 160, fontStyle: 'bold', textColor: TEXT_DARK },
      1: { cellWidth: contentWidth - 160 },
    },
    head: [['Location Name', 'Visual Description']],
    body: planner.locations.map((loc) => [loc.name, loc.visualDescription]),
  })

  // ------------------------------------------------------------------ Scene pages
  planner.scenes.forEach((scene) => {
    doc.addPage('a4', 'landscape')
    let sy = 52

    doc.setFont('helvetica', 'bold')
    doc.setFontSize(8.5)
    doc.setTextColor(...ACCENT)
    doc.text(`${filmTitle.toUpperCase()} • SCENE BREAKDOWN`, MARGIN, sy)

    sy += 22
    doc.setFontSize(16)
    doc.setTextColor(...TEXT_DARK)
    doc.text(`${scene.sceneId}: ${scene.sceneTitle}`, MARGIN, sy)

    const sceneTime = scene.shots.reduce((sum, s) => sum + (Number(s.durationSeconds) || 0), 0)
    sy += 18
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9.5)
    doc.setTextColor(...TEXT_BODY)
    const meta =
      `Locations: ${scene.locations.join(', ') || '—'} | Time of Day: ${scene.timeOfDay || '—'} | ` +
      `Shots: ${scene.shots.length} | Scene time: ${sceneTime}s`
    doc.text(doc.splitTextToSize(meta, contentWidth), MARGIN, sy)

    autoTable(doc, {
      ...baseTableOptions(),
      startY: sy + 14,
      columnStyles: {
        0: { cellWidth: 54, fontStyle: 'bold', textColor: TEXT_DARK }, // Shot ID
        1: { cellWidth: 28 }, // Duration
        2: { cellWidth: 64 }, // Framing (includes angle)
        3: { cellWidth: 72 }, // Camera movement
        4: { cellWidth: 58 }, // Characters
        5: { cellWidth: 62 }, // Location
        6: { cellWidth: 142 }, // What we see
        7: { cellWidth: 118 }, // Dialogue
        8: { cellWidth: 76 }, // Emotion
        9: { cellWidth: contentWidth - 674 }, // Sound
      },
      head: [
        [
          'Shot ID',
          'Dur.',
          'Framing',
          'Camera Movement',
          'Characters',
          'Location',
          'What We See (1 Frame)',
          'Dialogue (Speaker / Line / Delivery)',
          'Emotion',
          'Sound',
        ],
      ],
      body: scene.shots.map((shot) => [
        shot.shotId,
        `${shot.durationSeconds}s`,
        shot.framing,
        shot.cameraMovement || 'Static',
        shot.characters.join(', ') || 'None',
        shot.location,
        shot.whatWeSee,
        formatDialogue(shot),
        shot.emotion,
        shot.sound,
      ]),
      didParseCell: (data: CellHookData) => {
        if (data.section === 'body' && data.column.index === 7 && data.cell.raw !== 'None') {
          data.cell.styles.textColor = TEXT_DARK
        }
      },
    })
  })

  drawFooters(doc, filmTitle)
  return doc
}

export function exportShotPlannerToPdf(planner: ShotPlanner): void {
  const doc = buildShotPlannerPdf(planner)
  const safeSlug = (planner.overview.filmTitle || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
  doc.save(`${safeSlug || 'storyforge'}-shot-planner.pdf`)
}
