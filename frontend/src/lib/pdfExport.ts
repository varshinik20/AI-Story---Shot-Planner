import jsPDF from 'jspdf'
import autoTable from 'jspdf-autotable'
import type { ShotPlanner } from '@/types/planner'

/**
 * Modular client-side PDF generator structured after the hackathon reference layout.
 * Page 1: Film title, logline, statistics, creator's intent, characters, and locations.
 * Subsequent pages: Scene-wise shot tables containing all 10 required fields.
 * Designed as an isolated module so a backend PDF service can replace it cleanly later.
 */
export function exportShotPlannerToPdf(planner: ShotPlanner): void {
  const doc = new jsPDF({
    orientation: 'landscape',
    unit: 'pt',
    format: 'a4',
  })

  const pageWidth = doc.internal.pageSize.getWidth()
  const margin = 40
  let y = 44

  // Header bar
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(9)
  doc.setTextColor(16, 163, 127)
  doc.text('STORYFORGE • PRODUCTION SHOT PLANNER', margin, y)

  y += 22
  doc.setFontSize(22)
  doc.setTextColor(33, 33, 33)
  doc.text(planner.overview.filmTitle, margin, y)

  y += 18
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(10.5)
  doc.setTextColor(75, 85, 99)
  const loglineLines = doc.splitTextToSize(planner.overview.logline, pageWidth - margin * 2)
  doc.text(loglineLines, margin, y)
  y += loglineLines.length * 14 + 10

  // Statistics summary row
  autoTable(doc, {
    startY: y,
    margin: { left: margin, right: margin },
    theme: 'grid',
    headStyles: {
      fillColor: [249, 249, 249],
      textColor: [33, 33, 33],
      fontStyle: 'bold',
      fontSize: 8.5,
      lineColor: [229, 231, 235],
    },
    bodyStyles: {
      textColor: [33, 33, 33],
      fontSize: 9.5,
      lineColor: [229, 231, 235],
    },
    head: [['Scenes', 'Total Shots', 'Dialogue Lines', 'Running Time', 'Video Format', 'Frame Rate']],
    body: [
      [
        String(planner.overview.totalScenes),
        String(planner.overview.totalShots),
        String(planner.overview.dialogueLines),
        `${planner.overview.runningTimeSeconds}s`,
        planner.overview.videoFormat,
        planner.overview.frameRate,
      ],
    ],
  })

  y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 16

  // Creator's Intent
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(11)
  doc.setTextColor(33, 33, 33)
  doc.text("Creator's Intent", margin, y)
  y += 14
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9.5)
  doc.setTextColor(75, 85, 99)
  const intentLines = doc.splitTextToSize(planner.overview.creatorsIntent, pageWidth - margin * 2)
  doc.text(intentLines, margin, y)
  y += intentLines.length * 13 + 14

  // Characters table
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(11)
  doc.setTextColor(33, 33, 33)
  doc.text('Characters', margin, y)

  autoTable(doc, {
    startY: y + 6,
    margin: { left: margin, right: margin },
    theme: 'grid',
    headStyles: {
      fillColor: [243, 244, 246],
      textColor: [33, 33, 33],
      fontStyle: 'bold',
      fontSize: 8.5,
      lineColor: [229, 231, 235],
    },
    bodyStyles: {
      textColor: [33, 33, 33],
      fontSize: 8.5,
      lineColor: [229, 231, 235],
      cellPadding: 5,
    },
    head: [['Name', 'Role', 'Physical Appearance', 'Personality & Voice']],
    body: planner.characters.map((c) => [
      c.name,
      c.role,
      c.physicalAppearance,
      c.personalityAndVoice,
    ]),
  })

  y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 16

  // Locations table
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(11)
  doc.setTextColor(33, 33, 33)
  doc.text('Locations', margin, y)

  autoTable(doc, {
    startY: y + 6,
    margin: { left: margin, right: margin },
    theme: 'grid',
    headStyles: {
      fillColor: [243, 244, 246],
      textColor: [33, 33, 33],
      fontStyle: 'bold',
      fontSize: 8.5,
      lineColor: [229, 231, 235],
    },
    bodyStyles: {
      textColor: [33, 33, 33],
      fontSize: 8.5,
      lineColor: [229, 231, 235],
      cellPadding: 5,
    },
    head: [['Location Name', 'Visual Description']],
    body: planner.locations.map((loc) => [loc.name, loc.visualDescription]),
  })

  // Following pages: Scene-wise shot tables with all 10 required fields
  planner.scenes.forEach((scene) => {
    doc.addPage('a4', 'landscape')
    let sy = 42

    doc.setFont('helvetica', 'bold')
    doc.setFontSize(9)
    doc.setTextColor(16, 163, 127)
    doc.text(`${planner.overview.filmTitle.toUpperCase()} • SCENE BREAKDOWN`, margin, sy)

    sy += 18
    doc.setFontSize(14)
    doc.setTextColor(33, 33, 33)
    doc.text(`${scene.sceneId}: ${scene.sceneTitle}`, margin, sy)

    sy += 15
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9.5)
    doc.setTextColor(107, 114, 128)
    doc.text(
      `Locations: ${scene.locations.join(', ')}   |   Time of Day: ${scene.timeOfDay}   |   Shots: ${scene.shots.length}`,
      margin,
      sy
    )

    autoTable(doc, {
      startY: sy + 12,
      margin: { left: margin, right: margin },
      theme: 'grid',
      headStyles: {
        fillColor: [33, 33, 33],
        textColor: [255, 255, 255],
        fontStyle: 'bold',
        fontSize: 7.5,
        cellPadding: 4,
      },
      bodyStyles: {
        textColor: [33, 33, 33],
        fontSize: 7.5,
        cellPadding: 4,
        valign: 'top',
        lineColor: [229, 231, 235],
      },
      columnStyles: {
        0: { cellWidth: 52 }, // Shot ID
        1: { cellWidth: 34 }, // Duration
        2: { cellWidth: 66 }, // Framing
        3: { cellWidth: 64 }, // Movement
        4: { cellWidth: 62 }, // Characters
        5: { cellWidth: 64 }, // Location
        6: { cellWidth: 145 }, // What we see
        7: { cellWidth: 125 }, // Dialogue
        8: { cellWidth: 66 }, // Emotion
        9: { cellWidth: 84 }, // Sound
      },
      head: [
        [
          'Shot ID',
          'Dur.',
          'Framing',
          'Camera Movement',
          'Characters',
          'Location',
          'What We See',
          'Dialogue (Speaker / Line / Delivery)',
          'Emotion',
          'Sound',
        ],
      ],
      body: scene.shots.map((shot) => [
        shot.shotId,
        `${shot.durationSeconds}s`,
        shot.framing,
        shot.cameraMovement,
        shot.characters.join(', ') || '—',
        shot.location,
        shot.whatWeSee,
        shot.dialogue
          ? `${shot.dialogue.speaker}: "${shot.dialogue.line}" (${shot.dialogue.delivery})`
          : 'None',
        shot.emotion,
        shot.sound,
      ]),
    })
  })

  const safeSlug = planner.overview.filmTitle
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')

  doc.save(`${safeSlug || 'storyforge'}-shot-planner.pdf`)
}
