import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.settings")
import django

django.setup()

from scanners.handlers import (
    HandlerApproval,
    HandlerBuy,
    HandlerDeploy,
    HandlerMint,
    HandlerPromotion,
    HandlerTransferBurn,
)
from scanners.scanners import ScannerAbsolute
from src.networks.models import Network
from src.store.models import Collection, Status

if __name__ == "__main__":
    networks = Network.objects.all()
    for network in networks:
        ##################################################
        #                  PROMOTION SCANNER                   #
        ##################################################
        ScannerAbsolute(
            network=network,
            handler=HandlerPromotion,
        ).start()
        time.sleep(0.5)
        ##################################################
        #                  BUY SCANNER                   #
        ##################################################
        ScannerAbsolute(
            network=network,
            handler=HandlerBuy,
        ).start()
        time.sleep(0.5)
        for standard in ("ERC721", "ERC1155"):
            ##################################################
            #                 DEPLOY SCANNER                 #
            ##################################################
            ScannerAbsolute(
                network=network,
                contract_type=standard,
                handler=HandlerDeploy,
            ).start()
            time.sleep(0.5)

    ##################################################
    #                  MINT SCANNER                  #
    ##################################################
    # Ethereum
    collections = Collection.objects.scannerable().exclude(network__network_type="tron")
    for collection in collections:
        ScannerAbsolute(
            network=collection.network,
            handler=HandlerTransferBurn,
            contract_type=collection.standard,
            contract=collection.get_contract(),
            synced=not collection.status == Status.IMPORTING,
        ).start()
        time.sleep(0.5)
        if not collection.is_imported:
            ScannerAbsolute(
                network=collection.network,
                handler=HandlerMint,
                contract_type=collection.standard,
                contract=collection.get_contract(),
            ).start()
            time.sleep(0.5)
        ScannerAbsolute(
            network=collection.network,
            handler=HandlerApproval,
            contract_type=collection.standard,
            contract=collection.get_contract(),
        ).start()
        time.sleep(0.5)

    while True:
        time.sleep(60)
        updated_collections = Collection.objects.scannerable().exclude(
            network__network_type="tron"
        )
        new_collections = list(set(updated_collections) - set(collections))

        if new_collections:
            for collection in new_collections:
                ScannerAbsolute(
                    network=collection.network,
                    handler=HandlerTransferBurn,
                    contract=collection.get_contract(),
                    contract_type=collection.standard,
                    synced=not collection.status == Status.IMPORTING,
                ).start()
                time.sleep(0.5)
                if not collection.is_imported:
                    ScannerAbsolute(
                        network=collection.network,
                        handler=HandlerMint,
                        contract_type=collection.standard,
                        contract=collection.get_contract(),
                    ).start()
                    time.sleep(0.5)
                ScannerAbsolute(
                    network=collection.network,
                    handler=HandlerApproval,
                    contract_type=collection.standard,
                    contract=collection.get_contract(),
                ).start()
                time.sleep(0.5)

            collections = updated_collections
