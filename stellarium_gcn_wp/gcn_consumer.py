import logging
import threading
import time
from queue import Queue
from typing import Literal, List, Optional

from gcn_kafka import Consumer
from stellarium_gcn_wp.settings import Settings

logger = logging.getLogger(__name__)


class GCNConsumer:

    def __init__(self, queue: Queue,
                 start_on: Literal["first", "last", "next", "track"] = "last",
                 topics: Optional[List[str]] = None):
        if topics is None or len(topics) == 0:
            topics = ['gcn.classic.text.ICECUBE_ASTROTRACK_BRONZE',
                      'gcn.classic.text.ICECUBE_ASTROTRACK_GOLD']

        logger.info(f"Subscribing to topics: {topics}")

        self._queue = queue
        self._keep_running = False
        self._thread = None

        auto_offset = "earliest"
        if start_on == "next":
            auto_offset = "latest"

        kafka_logger = logger.getChild("kafka")
        kafka_logger.setLevel(logging.ERROR)
        config = {
            "auto.offset.reset": auto_offset,
            "max.poll.interval.ms": 30 * 60 * 1000,
            "logger": kafka_logger,
            "error_cb": lambda x: logger.info(f"Kafka error {x}"),
            "throttle_cb": lambda x: logger.info(f"Kafka throttle {x}")
        }

        self._tracking = False
        if start_on == "track":
            config["group.id"] = Settings.gcn_kafka_group_id
            config["enable.auto.commit"] = False
            self._tracking = True

        logger.debug(f"start_on={start_on}, tracking={self._tracking}, config={config}")
        self._consumer = Consumer(config=config,
                                  client_id=Settings.gcn_kafka_id,
                                  client_secret=Settings.gcn_kafka_secret)

        if start_on == "last":
            self._consumer.subscribe(topics,
                                     on_assign=self._latest_on_assign)
        else:
            self._consumer.subscribe(topics)

    @staticmethod
    def _latest_on_assign(consumer, partitions):
        # Moves the offset to one before the last message, so we get the last message
        # on the first consume()
        for part in partitions:
            newest_offset, last_offset = consumer.get_watermark_offsets(part)
            part.offset = max(newest_offset, last_offset - 1)
        consumer.assign(partitions)

    def start(self):
        logger.info("Starting GCN consumer")
        self._thread = threading.Thread(target=self._run)
        self._keep_running = True
        self._thread.start()

    def stop(self):
        logger.info("Stopping GCN consumer")
        self._keep_running = False
        if self._thread is not None:
            self._thread.join()

    def _run(self):
        while self._keep_running:
            if (message := self._consumer.poll(timeout=1)) is not None:
                if message.error():
                    logger.warning(message.error())
                    continue
                logger.info(f'topic={message.topic()}, offset={message.offset()}')
                value = message.value().decode()
                self._queue.put(item=value, block=True)

                if self._tracking:
                    logger.info("Waiting to commit..")
                    while self._queue.unfinished_tasks and self._keep_running:
                        time.sleep(1)

                    if self._keep_running:
                        logger.info(f"commiting topic={message.topic()} offset={message.offset()}")
                        self._consumer.commit(message)
