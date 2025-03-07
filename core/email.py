import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from pydantic import EmailStr

from core.config import settings

logger = logging.getLogger(__name__)


class EmailManager:
    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
        self.use_tls = settings.SMTP_USE_TLS

    async def send_email(
            self,
            to_email: List[EmailStr],
            subject: str,
            html_content: str,
            cc: Optional[List[EmailStr]] = None,
            bcc: Optional[List[EmailStr]] = None,
    ) -> bool:
        """
        이메일을 전송합니다.

        Args:
            to_email: 수신자 이메일 주소 목록
            subject: 이메일 제목
            html_content: HTML 형식의 이메일 내용
            cc: 참조 이메일 주소 목록
            bcc: 숨은 참조 이메일 주소 목록

        Returns:
            bool: 이메일 전송 성공 여부
        """
        try:
            msg = MIMEMultipart()
            msg["From"] = self.from_email
            msg["To"] = ", ".join(to_email)
            msg["Subject"] = subject

            if cc:
                msg["Cc"] = ", ".join(cc)
            if bcc:
                msg["Bcc"] = ", ".join(bcc)

            msg.attach(MIMEText(html_content, "html"))

            # SMTP 서버 연결 및 이메일 전송
            if self.use_tls:
                server = smtplib.SMTP(self.host, self.port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.host, self.port)

            server.login(self.username, self.password)

            all_recipients = to_email
            if cc:
                all_recipients.extend(cc)
            if bcc:
                all_recipients.extend(bcc)

            server.sendmail(self.from_email, all_recipients, msg.as_string())
            server.quit()

            logger.info(f"이메일 전송 성공: {to_email}")
            return True

        except Exception as e:
            logger.error(f"이메일 전송 실패: {e}")
            return False

    async def send_verification_email(self, email: EmailStr, verification_token: str) -> bool:
        """
        회원가입 인증 이메일을 전송합니다.

        Args:
            email: 사용자 이메일 주소
            verification_token: 인증 토큰

        Returns:
            bool: 이메일 전송 성공 여부
        """
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"

        html_content = f"""
        <html>
            <body>
                <h2>AI 챗봇 서비스 이메일 인증</h2>
                <p>안녕하세요, AI 챗봇 서비스에 가입해 주셔서 감사합니다.</p>
                <p>아래 링크를 클릭하여 이메일 인증을 완료해주세요:</p>
                <p><a href="{verification_url}">이메일 인증하기</a></p>
                <p>링크는 24시간 동안 유효합니다.</p>
                <p>감사합니다.</p>
            </body>
        </html>
        """

        return await self.send_email(
            to_email=[email],
            subject="AI 챗봇 서비스 이메일 인증",
            html_content=html_content
        )

    async def send_invitation_email(
            self,
            email: EmailStr,
            inviter_name: str,
            group_name: str,
            invitation_token: str
    ) -> bool:
        """
        그룹 초대 이메일을 전송합니다.

        Args:
            email: 초대할 사용자 이메일 주소
            inviter_name: 초대자 이름
            group_name: 그룹 이름
            invitation_token: 초대 토큰

        Returns:
            bool: 이메일 전송 성공 여부
        """
        invitation_url = f"{settings.FRONTEND_URL}/accept-invitation?token={invitation_token}"

        html_content = f"""
        <html>
            <body>
                <h2>AI 챗봇 서비스 그룹 초대</h2>
                <p>안녕하세요,</p>
                <p><strong>{inviter_name}</strong>님이 <strong>{group_name}</strong> 그룹에 초대했습니다.</p>
                <p>아래 링크를 클릭하여 초대를 수락하세요:</p>
                <p><a href="{invitation_url}">초대 수락하기</a></p>
                <p>링크는 7일 동안 유효합니다.</p>
                <p>감사합니다.</p>
            </body>
        </html>
        """

        return await self.send_email(
            to_email=[email],
            subject=f"AI 챗봇 서비스: {inviter_name}님이 {group_name} 그룹에 초대했습니다",
            html_content=html_content
        )


# 이메일 모듈 인스턴스 생성
email_manager = EmailManager()