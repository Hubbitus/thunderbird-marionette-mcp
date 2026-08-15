"""Generate TB prefs.js with a pre-configured IMAP account."""

from __future__ import annotations

from pathlib import Path


def write_imap_account_prefs(
    profile_dir: Path,
    *,
    email: str = "user@greenmail.local",
    username: str = "user",
    imap_host: str = "127.0.0.1",
    imap_port: int = 3143,
    smtp_host: str = "127.0.0.1",
    smtp_port: int = 3025,
) -> None:
    """Append IMAP account prefs to the profile's prefs.js.

    TB reads prefs.js at startup and treats these as authoritative. Written
    before TB launches, this bypasses the Account Setup Assistant.
    """
    profile_dir.mkdir(parents=True, exist_ok=True)
    prefs = profile_dir / "prefs.js"
    lines = [
        # Account definitions
        'user_pref("mail.account.account1.identities", "id1");\n',
        'user_pref("mail.account.account1.server", "server1");\n',
        'user_pref("mail.accountmanager.accounts", "account1");\n',
        'user_pref("mail.accountmanager.defaultaccount", "account1");\n',
        # Identity
        'user_pref("mail.identity.id1.fullName", "Test User");\n',
        f'user_pref("mail.identity.id1.useremail", "{email}");\n',
        'user_pref("mail.identity.id1.smtpServer", "smtp1");\n',
        # IMAP server
        'user_pref("mail.server.server1.type", "imap");\n',
        f'user_pref("mail.server.server1.hostname", "{imap_host}");\n',
        f'user_pref("mail.server.server1.port", {imap_port});\n',
        f'user_pref("mail.server.server1.userName", "{username}");\n',
        'user_pref("mail.server.server1.socketType", 0);\n',  # plain
        'user_pref("mail.server.server1.authMethod", 3);\n',  # cleartext
        f'user_pref("mail.server.server1.name", "{email}");\n',
        'user_pref("mail.server.server1.check_new_mail", false);\n',
        # SMTP
        'user_pref("mail.smtpservers", "smtp1");\n',
        f'user_pref("mail.smtpserver.smtp1.hostname", "{smtp_host}");\n',
        f'user_pref("mail.smtpserver.smtp1.port", {smtp_port});\n',
        f'user_pref("mail.smtpserver.smtp1.username", "{username}");\n',
        'user_pref("mail.smtpserver.smtp1.authMethod", 3);\n',
        'user_pref("mail.smtpserver.smtp1.try_ssl", 0);\n',
        # Disable first-run wizards
        'user_pref("mail.provider.suppress_dialog_on_startup", true);\n',
        'user_pref("app.donation.eoy.version.viewed", 999);\n',
        'user_pref("mailnews.start_page.enabled", false);\n',
    ]
    with prefs.open("a", encoding="utf-8") as fh:
        fh.writelines(lines)
