"""Management CLI commands."""

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from sqlalchemy import delete, func, select

from app.core.database import async_session_factory
from app.models.business import Business, generate_webhook_key
from app.models.message import Message
from app.models.tool_call import ToolCall
from app.models.usage_log import UsageLog
from app.models.user import User

ph = PasswordHasher()


async def _create_business(name: str, email: str, password: str) -> None:
    """Create a new business and owner user account."""
    async with async_session_factory() as session:
        try:
            # 1. Create Business
            business = Business(
                name=name,
                webhook_key=generate_webhook_key(),
            )
            session.add(business)
            await session.flush()

            # 2. Hash password with argon2
            password_hash = ph.hash(password)

            # 3. Create User
            user = User(
                business_id=business.id,
                email=email.strip().lower(),
                password_hash=password_hash,
            )
            session.add(user)
            await session.commit()

            print("==================================================")
            print("Business and Owner created successfully!")
            print(f"Business ID:   {business.id}")
            print(f"Business Name: {business.name}")
            print(f"Owner Email:   {user.email}")
            print(f"Webhook Key:   {business.webhook_key}")
            print("==================================================")
        except Exception as exc:
            await session.rollback()
            print(f"Error creating business: {exc}", file=sys.stderr)
            sys.exit(1)


async def _cleanup_retention(days: int = 90, dry_run: bool = False) -> None:
    """Purge messages, usage logs, and tool calls older than retention policy."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    print(f"Running data retention cleanup for records older than {days} days (cutoff: {cutoff.isoformat()})...")

    async with async_session_factory() as session:
        try:
            # Count records to be purged
            msg_count_q = select(func.count(Message.id)).where(Message.created_at < cutoff)
            usage_count_q = select(func.count(UsageLog.id)).where(UsageLog.created_at < cutoff)
            tool_count_q = select(func.count(ToolCall.id)).where(ToolCall.created_at < cutoff)

            msg_count = (await session.execute(msg_count_q)).scalar() or 0
            usage_count = (await session.execute(usage_count_q)).scalar() or 0
            tool_count = (await session.execute(tool_count_q)).scalar() or 0

            print(f"Found {msg_count} messages, {usage_count} usage logs, {tool_count} tool calls to purge.")

            if dry_run:
                print("Dry-run mode enabled: No database modifications made.")
                return

            # Execute deletes
            if msg_count > 0:
                await session.execute(delete(Message).where(Message.created_at < cutoff))
            if usage_count > 0:
                await session.execute(delete(UsageLog).where(UsageLog.created_at < cutoff))
            if tool_count > 0:
                await session.execute(delete(ToolCall).where(ToolCall.created_at < cutoff))

            await session.commit()
            print("Cleanup complete: purged records committed successfully.")
        except Exception as exc:
            await session.rollback()
            print(f"Error during retention cleanup: {exc}", file=sys.stderr)
            sys.exit(1)


async def _delete_customer_data(business_id_str: str, phone: str, dry_run: bool = False) -> None:
    """Purge all records associated with a specific customer in a business."""
    from uuid import UUID

    from app.models.conversation import Conversation
    from app.models.customer import Customer

    try:
        biz_id = UUID(business_id_str)
    except ValueError:
        print(f"Invalid business ID UUID: {business_id_str}", file=sys.stderr)
        sys.exit(1)

    clean_phone = phone.strip()
    print(f"Searching records for customer {clean_phone} in business {biz_id}...")

    async with async_session_factory() as session:
        try:
            cust_q = select(Customer).where(
                Customer.business_id == biz_id,
                Customer.phone == clean_phone,
            )
            customer = (await session.execute(cust_q)).scalar_one_or_none()
            if not customer:
                print(f"No customer found with phone {clean_phone} in business {biz_id}.")
                return

            convs_q = select(Conversation.id).where(
                Conversation.business_id == biz_id,
                Conversation.customer_id == customer.id,
            )
            conv_ids = (await session.execute(convs_q)).scalars().all()

            msg_count = 0
            tool_count = 0
            usage_count = 0
            if conv_ids:
                msg_count_q = select(func.count(Message.id)).where(Message.conversation_id.in_(conv_ids))
                tool_count_q = select(func.count(ToolCall.id)).where(ToolCall.conversation_id.in_(conv_ids))
                usage_count_q = select(func.count(UsageLog.id)).where(UsageLog.conversation_id.in_(conv_ids))

                msg_count = (await session.execute(msg_count_q)).scalar() or 0
                tool_count = (await session.execute(tool_count_q)).scalar() or 0
                usage_count = (await session.execute(usage_count_q)).scalar() or 0

            print(f"Records found: Customer ID: {customer.id}, Conversations: {len(conv_ids)}, "
                  f"Messages: {msg_count}, ToolCalls: {tool_count}, UsageLogs: {usage_count}")

            if dry_run:
                print("Dry-run mode enabled: No data was deleted.")
                return

            # Delete customer (cascades to conversations, messages, tool calls, usage logs)
            await session.delete(customer)
            await session.commit()
            print(f"Successfully deleted all data for customer {clean_phone}.")
        except Exception as exc:
            await session.rollback()
            print(f"Error deleting customer data: {exc}", file=sys.stderr)
            sys.exit(1)


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="WhatsApp Bot Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-business
    create_biz = subparsers.add_parser("create-business", help="Create a new business and owner")
    create_biz.add_argument("--name", required=True, help="Business name")
    create_biz.add_argument("--email", required=True, help="Owner email address")
    create_biz.add_argument("--password", required=True, help="Owner password")

    # cleanup-retention
    cleanup = subparsers.add_parser("cleanup-retention", help="Purge historical records older than X days")
    cleanup.add_argument("--days", type=int, default=90, help="Retention period in days (default: 90)")
    cleanup.add_argument("--dry-run", action="store_true", help="Report records without deleting")

    # delete-data
    del_data = subparsers.add_parser("delete-data", help="Purge customer data by business and phone")
    del_data.add_argument("--business-id", required=True, help="Business UUID")
    del_data.add_argument("--customer-phone", required=True, help="Customer phone number")
    del_data.add_argument("--dry-run", action="store_true", help="Report records without deleting")

    args = parser.parse_args()

    if args.command == "create-business":
        asyncio.run(_create_business(args.name, args.email, args.password))
    elif args.command == "cleanup-retention":
        asyncio.run(_cleanup_retention(args.days, args.dry_run))
    elif args.command == "delete-data":
        asyncio.run(_delete_customer_data(args.business_id, args.customer_phone, args.dry_run))


if __name__ == "__main__":
    main()

