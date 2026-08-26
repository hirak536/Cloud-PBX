"""
Shared HTML email templates for Cloud PBX.
"""

from datetime import date


def _base_template(title, preheader, body_html, login_url=None):
    year = date.today().year
    login_button = ''
    if login_url:
        login_button = f"""
          <!-- CTA Button -->
          <tr>
            <td style="background:#ffffff;padding:0 40px 40px;text-align:center;border-left:1px solid #e5e7eb;border-right:1px solid #e5e7eb;">
              <a href="{login_url}" target="_blank"
                 class="cta-btn"
                 style="display:inline-block;background-color:#2563eb;background:linear-gradient(135deg,#2563eb 0%,#1d4ed8 100%);color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;padding:14px 36px;border-radius:8px;letter-spacing:0.3px;box-shadow:0 4px 12px rgba(37,99,235,0.35);transition:transform 0.2s ease,box-shadow 0.2s ease;border:2px solid #1d4ed8;">
                Log In to Cloud PBX &rarr;
              </a>
            </td>
          </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title}</title>
  <style>
    @keyframes fadeSlideIn {{
      from {{ opacity: 0; transform: translateY(16px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}
    .email-card {{
      animation: fadeSlideIn 0.5s ease both;
    }}
    .cta-btn:hover {{
      transform: translateY(-2px) scale(1.03) !important;
      box-shadow: 0 8px 24px rgba(37,99,235,0.45) !important;
    }}
  </style>
</head>
<body style="margin:0;padding:0;background-color:#eef2f7;font-family:'Segoe UI',Helvetica,Arial,sans-serif;">
  <!-- preheader -->
  <span style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preheader}</span>

  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#eef2f7;padding:48px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

          <!-- Logo / Brand Bar -->
          <tr>
            <td style="padding:0 0 24px;text-align:center;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="text-align:center;">
                    <span style="display:inline-block;background-color:#1e3a5f;background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 100%);color:#ffffff;font-size:18px;font-weight:800;letter-spacing:1px;padding:10px 22px;border-radius:8px;border:2px solid #1e3a5f;">Cloud PBX</span>
                    <p style="margin:8px 0 0;color:#6b7280;font-size:12px;letter-spacing:0.5px;text-transform:uppercase;">Cloud Communications Solutions</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Card -->
          <tr>
            <td class="email-card" style="background:#ffffff;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,0.08);overflow:hidden;">
              <table width="100%" cellpadding="0" cellspacing="0">

                <!-- Accent stripe -->
                <tr>
                  <td style="background:linear-gradient(90deg,#1e3a5f 0%,#2563eb 60%,#60a5fa 100%);height:4px;font-size:0;line-height:0;">&nbsp;</td>
                </tr>

                <!-- Body -->
                <tr>
                  <td style="padding:40px 40px 32px;">
                    {body_html}
                  </td>
                </tr>

                {login_button}

              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:28px 0 0;text-align:center;">
              <p style="margin:0;color:#9ca3af;font-size:12px;line-height:1.8;">
                This is an automated message from Cloud PBX. Please do not reply to this email.
              </p>
              <p style="margin:4px 0 0;color:#9ca3af;font-size:12px;">
                &copy; {year} Cloud Communications Solutions. All rights reserved.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def password_reset_email(name, temp_password, login_url=None):
    """HTML email for admin-initiated password reset."""
    body = f"""
      <h2 style="margin:0 0 6px;color:#111827;font-size:24px;font-weight:700;letter-spacing:-0.5px;">Password Reset</h2>
      <p style="margin:0 0 28px;color:#6b7280;font-size:14px;border-bottom:1px solid #f3f4f6;padding-bottom:28px;">Your account password has been reset by an administrator.</p>

      <p style="margin:0 0 14px;color:#374151;font-size:15px;">Hello <strong style="color:#111827;">{name}</strong>,</p>
      <p style="margin:0 0 28px;color:#4b5563;font-size:15px;line-height:1.7;">
        Your password has been reset. Use the temporary password below to sign in.
        You will be required to set a new password immediately after logging in.
      </p>

      <!-- Password box -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
        <tr>
          <td style="background:#f0f7ff;border:1.5px solid #bfdbfe;border-radius:10px;padding:22px;text-align:center;">
            <p style="margin:0 0 8px;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;">Temporary Password</p>
            <p style="margin:0;color:#1e3a5f;font-size:26px;font-weight:700;letter-spacing:4px;font-family:'Courier New',monospace;">{temp_password}</p>
          </td>
        </tr>
      </table>

      <!-- Warning -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 8px;">
        <tr>
          <td style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:14px 16px;">
            <p style="margin:0;color:#92400e;font-size:13px;line-height:1.6;">
              <strong>&#9888; Important:</strong> This is a one-time temporary password. You must change it on your first login. Do not share it with anyone.
            </p>
          </td>
        </tr>
      </table>
    """
    return _base_template(
        title='Password Reset — Cloud PBX',
        preheader='Your Cloud PBX password has been reset. Use the temporary password to log in.',
        body_html=body,
        login_url=login_url,
    )


def forgot_password_email(name, temp_password, login_url=None):
    """HTML email for self-service forgot password."""
    body = f"""
      <h2 style="margin:0 0 6px;color:#111827;font-size:24px;font-weight:700;letter-spacing:-0.5px;">Password Reset Request</h2>
      <p style="margin:0 0 28px;color:#6b7280;font-size:14px;border-bottom:1px solid #f3f4f6;padding-bottom:28px;">We received a request to reset your Cloud PBX password.</p>

      <p style="margin:0 0 14px;color:#374151;font-size:15px;">Hello <strong style="color:#111827;">{name}</strong>,</p>
      <p style="margin:0 0 28px;color:#4b5563;font-size:15px;line-height:1.7;">
        A password reset was requested for your account. Use the temporary password below to sign in,
        then set a new password immediately.
      </p>

      <!-- Password box -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
        <tr>
          <td style="background:#f0f7ff;border:1.5px solid #bfdbfe;border-radius:10px;padding:22px;text-align:center;">
            <p style="margin:0 0 8px;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;">Temporary Password</p>
            <p style="margin:0;color:#1e3a5f;font-size:26px;font-weight:700;letter-spacing:4px;font-family:'Courier New',monospace;">{temp_password}</p>
          </td>
        </tr>
      </table>

      <!-- Warning -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 8px;">
        <tr>
          <td style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:14px 16px;">
            <p style="margin:0;color:#92400e;font-size:13px;line-height:1.6;">
              <strong>&#9888; Important:</strong> This password expires after first use. You will be prompted to create a new password upon login.
            </p>
          </td>
        </tr>
      </table>

      <p style="margin:16px 0 0;color:#9ca3af;font-size:13px;">If you did not request a password reset, you can safely ignore this email &mdash; your password will not change.</p>
    """
    return _base_template(
        title='Password Reset Request — Cloud PBX',
        preheader='Use the temporary password below to access your Cloud PBX account.',
        body_html=body,
        login_url=login_url,
    )


def welcome_email(name, username, temp_password, login_url=None, email=None):
    """HTML email sent when a new user account is created."""
    courier = "font-family:'Courier New',monospace;"
    email_row = (
        '<tr><td style="padding-top:16px;padding-bottom:16px;border-top:1px solid #dbeafe;">'
        '<p style="margin:0 0 6px;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;">Email</p>'
        f'<p style="margin:0;color:#1e3a5f;font-size:16px;font-weight:700;{courier}">{email}</p>'
        '</td></tr>'
    ) if email else ''
    body = f"""
      <h2 style="margin:0 0 6px;color:#111827;font-size:24px;font-weight:700;letter-spacing:-0.5px;">Welcome to Cloud PBX</h2>
      <p style="margin:0 0 28px;color:#6b7280;font-size:14px;border-bottom:1px solid #f3f4f6;padding-bottom:28px;">Your account has been created successfully.</p>

      <p style="margin:0 0 14px;color:#374151;font-size:15px;">Hello <strong style="color:#111827;">{name}</strong>,</p>
      <p style="margin:0 0 28px;color:#4b5563;font-size:15px;line-height:1.7;">
        An account has been created for you on Cloud PBX. Use the credentials below to sign in for the first time.
        You will be asked to set a new password on your first login.
      </p>

      <!-- Credentials box -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
        <tr>
          <td style="background:#f0f7ff;border:1.5px solid #bfdbfe;border-radius:10px;padding:22px;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding-bottom:16px;">
                  <p style="margin:0 0 6px;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;">Full Name</p>
                  <p style="margin:0;color:#1e3a5f;font-size:16px;font-weight:700;">{name}</p>
                </td>
              </tr>
              <tr>
                <td style="padding-top:16px;padding-bottom:16px;border-top:1px solid #dbeafe;">
                  <p style="margin:0 0 6px;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;">Username</p>
                  <p style="margin:0;color:#1e3a5f;font-size:18px;font-weight:700;font-family:'Courier New',monospace;">{username}</p>
                </td>
              </tr>
              {email_row}
              <tr>
                <td style="padding-top:16px;border-top:1px solid #dbeafe;">
                  <p style="margin:0 0 6px;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;">Temporary Password</p>
                  <p style="margin:0;color:#1e3a5f;font-size:22px;font-weight:700;letter-spacing:4px;font-family:'Courier New',monospace;">{temp_password}</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>

      <!-- Warning -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 8px;">
        <tr>
          <td style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:14px 16px;">
            <p style="margin:0;color:#92400e;font-size:13px;line-height:1.6;">
              <strong>&#9888; Action required:</strong> You must change your password on first login. Keep your credentials secure and do not share them.
            </p>
          </td>
        </tr>
      </table>

      <p style="margin:16px 0 0;color:#9ca3af;font-size:13px;">If you have any questions, please contact your administrator.</p>
    """
    return _base_template(
        title='Welcome to Cloud PBX',
        preheader='Your Cloud PBX account is ready. Log in with your temporary credentials.',
        body_html=body,
        login_url=login_url,
    )
