from datetime import datetime
from html import escape

from api.v1.superAdmin.schemas import EmailTemplateInput


GIET_LOGO = (
    "https://res.cloudinary.com/dxp6ojigf/image/upload/"
    "v1790921495/gietlogo-2_oomvrv.jpg"
)

SHRUJAN_LOGO = (
    "https://res.cloudinary.com/dxp6ojigf/image/upload/"
    "v1790921570/srjn-logo-2_to43jf.jpg"
)


WEBSITE_URL = "https://shrujangietu.in/"
INSTAGRAM_URL = (
    "https://www.instagram.com/gietuniversitygunupur_shrujan/"
)
YOUTUBE_URL = "https://www.youtube.com/c/GIETUniversityGunupur/streams"


def esc(value: str | None) -> str:
    """Escape user-provided text for safe HTML rendering."""
    return escape(value or "", quote=True)


def multiline(value: str | None) -> str:
    """Render plain text while preserving line breaks."""
    return esc(value).replace("\n", "<br>")


def build_email_html(data: EmailTemplateInput) -> str:
    # Greeting
    if data.recipient_name:
        greeting = f"Dear {esc(data.recipient_name)},"
    else:
        greeting = "Hello,"

    # Preheader (hidden preview text)
    preheader = ""
    if data.preheader:
        preheader = f"""
        <div style="
            display:none!important;
            font-size:1px;
            color:#ffffff;
            line-height:1px;
            max-height:0;
            max-width:0;
            opacity:0;
            overflow:hidden;
        ">
            {esc(data.preheader)}
        </div>
        """

    # Highlight section
    highlight = ""
    if data.highlight_title or data.highlight_message:
        highlight = f"""
        <table role="presentation" width="100%"
            cellpadding="0" cellspacing="0"
            style="margin:20px 0;
                   background-color:#fff9e9;
                   border:1px solid #f4d78c;
                   border-radius:8px;">
            <tr>
                <td width="58" align="center" valign="middle"
                    style="padding:15px 5px;">
                    <div style="
                        width:34px;height:34px;
                        line-height:34px;
                        border-radius:50%;
                        background-color:#fff0c2;
                        color:#bd8500;
                        font-size:22px;
                        font-weight:bold;
                        text-align:center;">
                        !
                    </div>
                </td>
                <td style="padding:15px 15px 15px 5px;
                           font-family:Arial,sans-serif;">
                    <div style="font-size:16px;
                                font-weight:bold;
                                color:#815900;
                                margin-bottom:6px;">
                        {esc(data.highlight_title)}
                    </div>
                    <div style="font-size:14px;
                                line-height:1.7;
                                color:#393939;">
                        {multiline(data.highlight_message)}
                    </div>
                </td>
            </tr>
        </table>
        """

    # Secondary description
    secondary = ""
    if data.secondary_description:
        secondary = f"""
        <div style="
            margin:18px 0;
            padding:15px;
            border:1px solid #e6d7f3;
            border-radius:7px;
            color:#55516a;
            font-size:14px;
            line-height:1.8;
        ">
            {multiline(data.secondary_description)}
        </div>
        """

    # Important section
    important = ""
    if data.important_title or data.important_message:
        important = f"""
        <table role="presentation" width="100%"
            cellpadding="0" cellspacing="0"
            style="margin:20px 0;
                   background-color:#fff0f3;
                   border:1px solid #f3a4b6;
                   border-radius:8px;">
            <tr>
                <td width="58" align="center" valign="middle"
                    style="padding:15px 5px;">
                    <div style="
                        width:34px;height:34px;
                        line-height:34px;
                        border-radius:50%;
                        background-color:#ffe0e8;
                        color:#c51c55;
                        font-size:22px;
                        font-weight:bold;
                        text-align:center;">
                        !
                    </div>
                </td>
                <td style="padding:15px 15px 15px 5px;
                           font-family:Arial,sans-serif;">
                    <div style="font-size:16px;
                                font-weight:bold;
                                color:#a7194a;
                                margin-bottom:6px;">
                        {esc(data.important_title)}
                    </div>
                    <div style="font-size:14px;
                                line-height:1.7;
                                color:#393939;">
                        {multiline(data.important_message)}
                    </div>
                </td>
            </tr>
        </table>
        """

    # Event details: only show fields that have values.
    event_fields = []

    if data.event_start_datetime:
        dt = data.event_start_datetime
        date_time = dt.strftime("%d %B %Y, %I:%M %p")
        if dt.tzinfo is not None and dt.utcoffset() is not None:
            date_time += f" {dt.tzname() or dt.strftime('%z')}"

        event_fields.append(("DATE & TIME", date_time, "▦"))

    if data.event_name:
        event_fields.append(("EVENT NAME", data.event_name, "◆"))

    if data.event_venue:
        event_fields.append(("VENUE", data.event_venue, "⌖"))

    event_details = ""
    if event_fields:
        count = len(event_fields)
        width = 100 / count
        cells = ""

        for index, (label, value, symbol) in enumerate(event_fields):
            border_right = (
                "border-right:1px solid #ded8eb;"
                if index < count - 1 else ""
            )
            cells += f"""
            <td width="{width:.2f}%"
                valign="top" align="center"
                style="padding:12px 6px;
                       {border_right}
                       font-family:Arial,sans-serif;">
                <div style="
                    width:38px;height:38px;
                    line-height:38px;
                    margin:0 auto 10px;
                    border-radius:50%;
                    background-color:#7025a8;
                    color:#ffffff;
                    font-size:20px;
                    text-align:center;">
                    {symbol}
                </div>
                <div style="
                    font-size:12px;
                    font-weight:bold;
                    color:#7025a8;
                    margin-bottom:8px;">
                    {label}
                </div>
                <div style="
                    font-size:14px;
                    line-height:1.5;
                    color:#29233a;
                    overflow-wrap:anywhere;">
                    {esc(value)}
                </div>
            </td>
            """

        event_details = f"""
        <table role="presentation" width="100%"
            cellpadding="0" cellspacing="0"
            style="margin:24px 0;
                   border:1px solid #e3dced;
                   border-radius:8px;">
            <tr>
                <td colspan="{count}" align="center"
                    style="padding:18px 8px 8px;
                           font-family:Arial,sans-serif;
                           font-size:18px;
                           font-weight:bold;
                           color:#54218b;">
                    ✣ &nbsp; EVENT DETAILS &nbsp; ✣
                </td>
            </tr>
            <tr>
                {cells}
            </tr>
        </table>
        """

    # Fixed website button
    website_button = f"""
    <table role="presentation" align="center"
        cellpadding="0" cellspacing="0"
        style="margin:22px auto;">
        <tr>
            <td align="center" bgcolor="#7025a8"
                style="border-radius:7px;
                       background-color:#7025a8;
                       background-image:linear-gradient(
                           90deg,#d51d7c,#7025a8
                       );">
                <a href="{WEBSITE_URL}"
                   target="_blank"
                   style="display:inline-block;
                          padding:14px 45px;
                          font-family:Arial,sans-serif;
                          font-size:15px;
                          font-weight:bold;
                          color:#ffffff;
                          text-decoration:none;">
                    VISIT WEBSITE
                </a>
            </td>
        </tr>
    </table>
    """

    closing = f"""
    <div style="
        margin:24px 0 8px;
        text-align:center;
        font-family:Arial,sans-serif;
        font-size:14px;
        line-height:1.8;
        color:#55516a;">
        {multiline(data.closing_message)}
        <br><br>
        Warm Regards,<br>
        <strong style="color:#7025a8;">
            GIET University
        </strong><br>
        Organizing Committee
    </div>
    """

    year = datetime.now().year

    # Complete email HTML
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport"
      content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light">
<title>{esc(data.subject)}</title>
<style>
    @media only screen and (max-width:600px) {{
        .email-container {{
            width:100% !important;
        }}
        .email-content {{
            padding:20px 16px !important;
        }}
        .brand-logo {{
            max-width:75px !important;
            height:auto !important;
        }}
        .brand-title {{
            font-size:17px !important;
        }}
        .event-cell {{
            padding:8px 3px !important;
        }}
    }}
</style>
</head>
<body style="
    margin:0;
    padding:0;
    background-color:#f2f0f7;
    font-family:Arial,Helvetica,sans-serif;
    color:#24212b;
">
{preheader}
<table role="presentation" width="100%"
       cellpadding="0" cellspacing="0"
       bgcolor="#f2f0f7">
<tr>
<td align="center" style="padding:18px 8px;">

<table role="presentation" class="email-container"
       width="600" cellpadding="0" cellspacing="0"
       bgcolor="#ffffff"
       style="width:100%;max-width:600px;
              border:1px solid #e7e1ef;">

<!-- HEADER -->
<tr>
<td bgcolor="#21134b"
    style="padding:20px 15px;
           background-color:#21134b;
           border-top:5px solid #b20a91;">
<table role="presentation" width="100%"
       cellpadding="0" cellspacing="0">
<tr>
<td width="20%" align="center" valign="middle">
    <img src="{GIET_LOGO}"
         alt="GIET University"
         class="brand-logo"
         width="100"
         style="display:block;width:100%;
                max-width:100px;height:auto;
                border:0;">
</td>
<td width="58%" align="left" valign="middle"
    style="padding:0 8px;">
    <div class="brand-title"
         style="font-size:22px;font-weight:bold;
                color:#ffffff;line-height:1.4;">
        GIET UNIVERSITY
    </div>
    <div style="font-size:13px;
                color:#eee8f8;margin-top:3px;">
        GUNUPUR, ODISHA
    </div>
    <div style="height:2px;background:#e2c84e;
                margin:9px 0;width:100%;"></div>
    <div style="font-size:12px;color:#e2c84e;">
        EXCELLENCE - OUR ESSENCE
    </div>
</td>
<td width="22%" align="center" valign="middle">
    <img src="{SHRUJAN_LOGO}"
         alt="Shrujan"
         class="brand-logo"
         width="115"
         style="display:block;width:100%;
                max-width:115px;height:auto;
                border:0;">
</td>
</tr>
</table>
</td>
</tr>

<!-- MAIN CONTENT -->
<tr>
<td class="email-content"
    style="padding:32px 30px 25px;">

    <h1 style="margin:0 0 20px;
               font-size:25px;
               line-height:1.35;
               color:#7025a8;">
        {esc(data.heading)}
    </h1>

    <p style="font-size:15px;
              line-height:1.7;
              margin:0 0 16px;
              color:#292631;">
        {greeting}
    </p>

    <div style="font-size:15px;
                line-height:1.8;
                color:#292631;">
        {multiline(data.main_message)}
    </div>

    {highlight}

    {secondary}

    {important}

    {event_details}

    {website_button}

    {closing}

</td>
</tr>

<!-- FOOTER -->
<tr>
<td bgcolor="#21134b"
    style="padding:20px 16px;
           background-color:#21134b;
           border-top:5px solid #a20a99;
           color:#ffffff;">
<table role="presentation" width="100%"
       cellpadding="0" cellspacing="0">
<tr>
<td valign="middle" width="58%"
    style="font-size:12px;line-height:1.9;
           color:#ffffff;padding-right:8px;">
    For any queries, contact us at<br>
    <a href="mailto:events@giet.edu"
       style="color:#ffffff;text-decoration:none;">
        events@giet.edu
    </a>
    &nbsp;|&nbsp;
    <a href="tel:+919937624703"
       style="color:#ffffff;text-decoration:none;">
        +91 9937624703
    </a>
</td>
<td valign="middle" align="right"
    width="42%"
    style="font-size:12px;line-height:2;
           color:#ffffff;">
    Follow us<br>
    <a href="{INSTAGRAM_URL}"
       style="color:#ffffff;text-decoration:underline;">
        Instagram
    </a>
    &nbsp;|&nbsp;
    <a href="{YOUTUBE_URL}"
       style="color:#ffffff;text-decoration:underline;">
        YouTube
    </a>
</td>
</tr>
</table>
</td>
</tr>

<tr>
<td bgcolor="#2c175d" align="center"
    style="padding:12px 8px;
           background-color:#2c175d;
           color:#d9cde9;
           font-size:11px;
           line-height:1.5;">
    &copy; {year} GIET University, Gunupur, Odisha.
    All rights reserved.
</td>
</tr>

</table>
</td>
</tr>
</table>
</body>
</html>"""
