import { NextRequest, NextResponse } from 'next/server'
import nodemailer from 'nodemailer'
import { z } from 'zod'

const contactSchema = z.object({
  name: z.string().min(1).max(200),
  email: z.string().email().max(200),
  institution: z.string().max(200).optional(),
  reason: z.enum([
    'campaign',
    'sensebox-bike',
    'temperature-logger',
    'sensebox-edu',
  ]),
  period: z.string().max(200).optional(),
  message: z.string().max(5000).optional(),
})

function getTransporter() {
  const host = process.env.CONTACT_SMTP_HOST
  const port = Number(process.env.CONTACT_SMTP_PORT ?? '587')
  const user = process.env.CONTACT_SMTP_USER
  const pass = process.env.CONTACT_SMTP_PASS

  if (!host || !user || !pass) {
    return null
  }

  return nodemailer.createTransport({
    host,
    port,
    secure: port === 465,
    auth: { user, pass },
  })
}

function getRecipients(): string[] {
  const raw = process.env.CONTACT_RECIPIENTS ?? ''
  return raw
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)
}

// Labels used in the email body — server-side only, kept in German as the
// authoritative language for internal notifications.
const reasonLabels: Record<string, string> = {
  campaign: 'Interesse an einer Kampagne',
  'sensebox-bike': 'senseBox:bike ausleihen',
  'temperature-logger': 'Temperatur Logger ausleihen',
  'sensebox-edu': 'senseBox:edu ausleihen',
}

export async function POST(request: NextRequest) {
  let body: unknown
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }

  const parsed = contactSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Validation failed', details: parsed.error.flatten() },
      { status: 422 },
    )
  }

  const { name, email, institution, reason, period, message } = parsed.data

  const recipients = getRecipients()
  if (recipients.length === 0) {
    // No recipients configured — log and return success so the form still
    // appears to work in development/preview environments.
    console.warn(
      '[contact] CONTACT_RECIPIENTS is not configured, skipping email send.',
    )
    return NextResponse.json({ ok: true })
  }

  const transporter = getTransporter()
  if (!transporter) {
    console.error('[contact] SMTP is not configured.')
    return NextResponse.json(
      { error: 'Mail service not configured' },
      { status: 503 },
    )
  }

  const reasonLabel = reasonLabels[reason] ?? reason

  const textBody = [
    `Name: ${name}`,
    `E-Mail: ${email}`,
    institution ? `Institution: ${institution}` : null,
    `Grund: ${reasonLabel}`,
    period ? `Zeitraum: ${period}` : null,
    message ? `\nNachricht:\n${message}` : null,
  ]
    .filter(Boolean)
    .join('\n')

  const htmlBody = `
    <table style="font-family:sans-serif;font-size:14px;border-collapse:collapse">
      <tr><td style="padding:4px 8px;font-weight:bold;color:#555">Name</td><td style="padding:4px 8px">${name}</td></tr>
      <tr><td style="padding:4px 8px;font-weight:bold;color:#555">E-Mail</td><td style="padding:4px 8px"><a href="mailto:${email}">${email}</a></td></tr>
      ${institution ? `<tr><td style="padding:4px 8px;font-weight:bold;color:#555">Institution</td><td style="padding:4px 8px">${institution}</td></tr>` : ''}
      <tr><td style="padding:4px 8px;font-weight:bold;color:#555">Grund</td><td style="padding:4px 8px">${reasonLabel}</td></tr>
      ${period ? `<tr><td style="padding:4px 8px;font-weight:bold;color:#555">Zeitraum</td><td style="padding:4px 8px">${period}</td></tr>` : ''}
    </table>
    ${message ? `<p style="font-family:sans-serif;font-size:14px;margin-top:16px"><strong>Nachricht:</strong><br/>${message.replace(/\n/g, '<br/>')}</p>` : ''}
  `

  try {
    await transporter.sendMail({
      from: process.env.CONTACT_SMTP_FROM ?? process.env.CONTACT_SMTP_USER,
      to: recipients.join(', '),
      replyTo: email,
      subject: `[Green City Heilbronn Kontakt] ${reasonLabel} – ${name}`,
      text: textBody,
      html: htmlBody,
    })
  } catch (err) {
    console.error('[contact] Failed to send email:', err)
    return NextResponse.json({ error: 'Failed to send email' }, { status: 500 })
  }

  return NextResponse.json({ ok: true })
}
