def get_welcome_email(user_name: str, project_name: str = "Startup API"):
    """
    Returns a dictionary containing the Subject and HTML Body for a welcome email.
    """
    subject = f"Welcome to {project_name}, {user_name}!"
    
    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ width: 80%; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px; }}
            .header {{ background-color: #f4f4f4; padding: 10px; text-align: center; border-radius: 10px 10px 0 0; }}
            .footer {{ font-size: 0.8em; color: #777; margin-top: 20px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Welcome to {project_name}!</h2>
            </div>
            <p>Hi {user_name},</p>
            <p>Thank you for joining us. We are excited to have you on board!</p>
            <p>Feel free to explore your dashboard and let us know if you have any questions.</p>
            <div class="footer">
                <p>&copy; 2024 {project_name}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return {
        "subject": subject,
        "body": body
    }




def verify_email(user_name, verification_link):
    logo_url = "https://cdn.imageurlgenerator.com/uploads/0aa56469-7caa-4861-9ca5-f95327e3e9b9.png"
    support_email = "suppor.sjn@gmail.com"
    
    subject = "Verify your email address"
    
    html_body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Verify Your Email</title>
        <style>
            /* Reset & Base Styles */
            body {{
                margin: 0;
                padding: 0;
                width: 100% !important;
                background-color: #f4f6f9;
                font-family: Arial, Helvetica, sans-serif;
                -webkit-text-size-adjust: 100%;
                -ms-text-size-adjust: 100%;
            }}
            table {{
                border-spacing: 0;
                border-collapse: collapse;
            }}
            img {{
                border: 0;
                line-height: 100%;
                outline: none;
                text-decoration: none;
            }}
            
            /* Responsive Utilities */
            @media screen and (max-width: 600px) {{
                .email-container {{
                    width: 100% !important;
                    padding-left: 16px !important;
                    padding-right: 16px !important;
                }}
                .content-box {{
                    padding: 24px 18px !important;
                }}
                .btn-wrapper {{
                    display: block !important;
                    width: 100% !important;
                }}
                .btn {{
                    display: block !important;
                    width: 100% !important;
                    text-align: center !important;
                    box-sizing: border-box;
                }}
            }}
        </style>
    </head>
    <body style="margin: 0; padding: 20px 0; background-color: #f4f6f9;">
        <center>
            <!-- Main Wrapper Table -->
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f4f6f9; margin: 0; padding: 0;">
                <tr>
                    <td align="center" style="padding: 10px 0;">
                        <!-- Content Container -->
                        <table role="presentation" class="email-container" width="600" cellpadding="0" cellspacing="0" border="0" style="width: 600px; max-width: 600px; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                            
                            <!-- Header / Logo -->
                            <tr>
                                <td align="center" style="padding: 30px 20px 20px 20px; background-color: #ffffff; border-bottom: 1px solid #f0f0f0;">
                                    <img src="{logo_url}" alt="Company Logo" width="140" style="display: block; max-width: 160px; height: auto; border: 0;" />
                                </td>
                            </tr>
                            
                            <!-- Body Content -->
                            <tr>
                                <td class="content-box" style="padding: 32px 40px; color: #333333; font-size: 15px; line-height: 1.6;">
                                    <h2 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 700; color: #111827;">Hello {user_name},</h2>
                                    <p style="margin: 0 0 20px 0; color: #4b5563;">Thank you for signing up! Please verify your email address to activate your account and access all features.</p>
                                    
                                    <!-- Call to Action Button -->
                                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 28px 0;">
                                        <tr>
                                            <td align="center">
                                                <table role="presentation" cellpadding="0" cellspacing="0" border="0" class="btn-wrapper">
                                                    <tr>
                                                        <td align="center" style="border-radius: 6px; background-color: #007bff;">
                                                            <a href="{verification_link}" class="btn" target="_blank" style="font-size: 15px; font-weight: bold; color: #ffffff; text-decoration: none; border-radius: 6px; padding: 14px 28px; display: inline-block; background-color: #007bff; border: 1px solid #007bff;">Verify Email Address</a>
                                                        </td>
                                                    </tr>
                                                </table>
                                            </td>
                                        </tr>
                                    </table>
                                    
                                    <!-- Fallback Link -->
                                    <p style="margin: 0 0 8px 0; font-size: 13px; color: #6b7280;">If the button above doesn't work, copy and paste the following link into your browser:</p>
                                    <p style="margin: 0 0 28px 0; font-size: 13px; word-break: break-all;"><a href="{verification_link}" style="color: #007bff; text-decoration: underline;">{verification_link}</a></p>
                                    
                                    <!-- Notes Container -->
                                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #fff8f6; border-left: 4px solid #d9534f; border-radius: 4px; margin-bottom: 24px;">
                                        <tr>
                                            <td style="padding: 14px 16px; font-size: 13px; line-height: 1.5; color: #333333;">
                                                <p style="margin: 0 0 8px 0; color: #d9534f; font-weight: bold;">Important Notes:</p>
                                                <ul style="margin: 0; padding-left: 18px; color: #4b5563;">
                                                    <td style="padding-bottom: 6px;"><strong>Expiry:</strong> This verification link is valid for <strong>15 minutes</strong> only.</td>
                                                    <tr></tr>
                                                    <td><strong>Unauthorized Registration?</strong> If you did not create this account, please contact our support team immediately at <a href="mailto:{support_email}" style="color: #007bff; font-weight: bold; text-decoration: none;">{support_email}</a>.</td>
                                                </ul>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                            
                            <!-- Footer -->
                            <tr>
                                <td align="center" style="padding: 20px; background-color: #f9fafb; border-top: 1px solid #f0f0f0; font-size: 12px; color: #9ca3af; text-align: center;">
                                    <p style="margin: 0 0 6px 0;">This email was sent automatically. Please do not reply directly to this message.</p>
                                    <p style="margin: 0;">Need help? Reach out to <a href="mailto:{support_email}" style="color: #6b7280; text-decoration: underline;">{support_email}</a></p>
                                </td>
                            </tr>
                            
                        </table>
                    </td>
                </tr>
            </table>
        </center>
    </body>
    </html>
    """
    
    return subject, html_body






def generate_password_reset_email(username, url, email):
    subject = "Password Reset Request"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            .container {{ font-family: sans-serif; line-height: 1.6; color: #333; max-width: 600px; }}
            .button {{ background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; }}
            .footer {{ font-size: 0.8em; color: #777; margin-top: 20px; border-top: 1px solid #eee; padding-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Password Reset Request</h2>
            <p>Hello <strong>{username}</strong>,</p>
            <p>We received a request to reset the password for the account associated with <strong>{email}</strong>.</p>
            <p>To proceed with the reset, please click the button below:</p>
            <p>
                <a href="{url}" class="button">Reset Password</a>
            </p>
            <p>If the button above doesn't work, copy and paste this link into your browser:</p>
            <p>{url}</p>
            <hr>
            <p><strong>Note:</strong> If you did not request this change, you can safely ignore this email. No action is required on your part, and your password will remain the same.</p>
            <div class="footer">
                <p>This is an automated message. Please do not reply directly to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return subject, html_body

def get_welcome_email(name):
    """
    Returns a tuple containing a Subject line and an HTML body 
    for a platform welcome email.
    """
    subject = f"Welcome to the Platform, {name}! 🚀"
    
    # Replace this with your actual logo or welcome banner URL
    image_link = "https://cdn.corenexis.com/files/c/9969145720.png"
    platform_url = "https://yourplatform.com/dashboard"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Welcome Email</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f4;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%">
            <tr>
                <td align="center" style="padding: 20px 0;">
                    <table border="0" cellpadding="0" cellspacing="0" width="600" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        <!-- Header Image -->
                        <tr>
                            <td align="center" style="background-color: #007bff;">
                                <img src="{image_link}" alt="Welcome to our Platform" width="600" style="display: block; width: 100%; max-width: 600px; height: auto;">
                            </td>
                        </tr>
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px; text-align: left;">
                                <h1 style="color: #333333; margin-top: 0;">Welcome aboard, {name}!</h1>
                                <p style="color: #555555; font-size: 16px; line-height: 1.5;">
                                    We're thrilled to have you join our community. Our platform is designed to help you achieve your goals faster and more efficiently.
                                </p>
                                <p style="color: #555555; font-size: 16px; line-height: 1.5;">
                                    To get started, click the button below to explore your new dashboard:
                                </p>
                                <div style="text-align: center; margin: 30px 0;">
                                    <a href="{platform_url}" style="background-color: #28a745; color: white; padding: 15px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px;">Get Started Now</a>
                                </div>
                                <p style="color: #777777; font-size: 14px;">
                                    If you have any questions, simply reply to this email. We're here to help!
                                </p>
                            </td>
                        </tr>
                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #f8f9fa; padding: 20px; text-align: center; color: #999999; font-size: 12px;">
                                &copy; 2026 Your Platform Name. All rights reserved.
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return subject, html_body


# You can now pass mail_html to your SMTP library (like smtplib)