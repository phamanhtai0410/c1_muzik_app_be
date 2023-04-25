import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask

from src.networks.models import Network, Provider
from src.rates.models import UsdRate
from src.settings import config
from src.support.models import Config, EmailConfig, EmailTemplate


class Command(BaseCommand):
    """Provide initial db fixtures from config with 'manage.py create_fixtures.py'"""

    @transaction.atomic
    def handle(self, *args, **options):
        help = "Create initial fixtures for Networks, Usd rates and Master user"  # noqa F841

        """Create Network objects"""
        for network in config.NETWORKS:
            Network.objects.get_or_create(
                name=network.name,
                needs_middleware=network.needs_middleware,
                native_symbol=network.native_symbol,
                fabric721_address=network.fabric721_address,
                fabric1155_address=network.fabric1155_address,
                exchange_address=network.exchange_address,
                promotion_address=network.promotion_address,
                platform_fee_address=network.platform_fee_address,
                platform_fee_percentage=network.platform_fee_percentage,
                network_type=network.network_type,
                deadline=timedelta(seconds=network.deadline),
                chain_id=network.chain_id,
            )

        """Create Provider objects"""
        for provider in config.PROVIDERS:
            Provider.objects.get_or_create(
                endpoint=provider.endpoint,
                network=Network.objects.get(name__iexact=provider.network),
            )

        """Create UsdRates objects"""
        for usd_rate in config.USD_RATES:
            UsdRate.objects.get_or_create(
                coin_node=usd_rate.coin_node,
                symbol=usd_rate.symbol,
                name=usd_rate.name,
                image=usd_rate.image,
                address=usd_rate.address,
                network=Network.objects.get(name__iexact=usd_rate.network),
                decimal=usd_rate.decimal,
            )

        """Create Intervals for Celery"""
        for interval in config.INTERVALS:
            IntervalSchedule.objects.get_or_create(
                pk=interval.pk,
                every=interval.every,
                period=getattr(IntervalSchedule, interval.period),
            )

        """Create Crontabs for Celery"""
        for crontab in config.CRONTABS:
            CrontabSchedule.objects.get_or_create(
                pk=crontab.pk,
                minute=crontab.minute,
                hour=crontab.hour,
            )

        """Create Periodic task for Celery"""
        for periodic_task in config.PERIODIC_TASKS:
            PeriodicTask.objects.get_or_create(
                name=periodic_task.name,
                task=periodic_task.task,
                interval=IntervalSchedule.objects.get(id=periodic_task.interval)
                if periodic_task.interval
                else None,
                crontab=CrontabSchedule.objects.get(id=periodic_task.crontab)
                if periodic_task.crontab
                else None,
                enabled=True,
            )

        """Create SupportEmail objects"""
        if EmailConfig.objects.exists():
            logging.info("email config exist, skipping")
        else:
            for email in config.EMAILS:
                email_data = EmailConfig(
                    role=email.role,
                    address=email.address,
                )
                for field_name in ("password", "smtp", "port", "use_tls"):
                    if getattr(email, field_name):
                        setattr(email_data, field_name, getattr(email, field_name))
                email_data.save()

        """Create config instance"""
        Config.objects.create(
            approval_timeout=config.SCANNER_SLEEP,
            max_royalty_percentage=config.MAX_ROYALTY_PERCENTAGE,
        )

        """Create Email Templates for all types"""
        for message_type in EmailTemplate.MessageType:
            EmailTemplate.objects.get_or_create(
                message_type=message_type,
            )
