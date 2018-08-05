import base64
import os
import signal
import time
import ujson
from typing import Any

import pytest
from google.protobuf.json_format import MessageToJson

from proto_build.message_pb2 import Person
from run_test_service_helper import start_service
from tomodachi.protocol.proto_build.protobuf.sns_sqs_message_pb2 import SNSSQSMessage
from tomodachi.validation.validation import validate_field_regex, \
    RegexMissmatchException


def test_json_base(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/dummy_service.py', monkeypatch)

    instance = services.get('test_dummy')

    async def _async() -> None:
        data = {'key': 'value'}
        t1 = time.time()
        json_message = await instance.message_protocol.build_message(instance, 'topic', data)
        t2 = time.time()
        result, message_uuid, timestamp = await instance.message_protocol.parse_message(json_message)
        assert result.get('data') == data
        assert result.get('metadata', {}).get('data_encoding') == 'raw'
        assert len(ujson.dumps(result.get('data'))) == len(ujson.dumps(data))
        assert ujson.dumps(result.get('data')) == ujson.dumps(data)
        assert len(message_uuid) == 73
        assert message_uuid[0:36] == instance.uuid
        assert timestamp >= t1
        assert timestamp <= t2

    loop.run_until_complete(_async())

    os.kill(os.getpid(), signal.SIGINT)
    loop.run_until_complete(future)


def test_json_base_large_message(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/dummy_service.py', monkeypatch)

    instance = services.get('test_dummy')

    async def _async() -> None:
        data = ['item {}'.format(i) for i in range(1, 10000)]
        assert len(ujson.dumps(data)) > 60000
        t1 = time.time()
        json_message = await instance.message_protocol.build_message(instance, 'topic', data)
        assert len(ujson.dumps(json_message)) < 60000
        t2 = time.time()
        result, message_uuid, timestamp = await instance.message_protocol.parse_message(json_message)
        assert result.get('metadata', {}).get('data_encoding') == 'base64_gzip_json'
        assert len(ujson.dumps(result.get('data'))) == len(ujson.dumps(data))
        assert ujson.dumps(result.get('data')) == ujson.dumps(data)
        assert len(message_uuid) == 73
        assert message_uuid[0:36] == instance.uuid
        assert timestamp >= t1
        assert timestamp <= t2

    loop.run_until_complete(_async())

    os.kill(os.getpid(), signal.SIGINT)
    loop.run_until_complete(future)


def test_protobuf_base(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/dummy_protobuf_service.py', monkeypatch)

    instance = services.get('test_dummy_protobuf')

    async def _async() -> None:
        data = Person()
        data.name = 'John Doe'
        data.id = '12'
        t1 = time.time()
        protobuf_message = await instance.message_protocol.build_message(instance, 'topic', data)
        t2 = time.time()
        result, message_uuid, timestamp = await instance.message_protocol.parse_message(protobuf_message, Person)
        assert type(result.get('data')) is Person
        assert result.get('data') == data
        assert result.get('metadata', {}).get('data_encoding') == 'proto'
        assert result.get('data') == data
        assert result.get('data').name == data.name
        assert result.get('data').id == data.id
        assert len(MessageToJson(result.get('data'))) == len(MessageToJson(data))
        assert MessageToJson(result.get('data')) == MessageToJson(data)
        assert len(message_uuid) == 73
        assert message_uuid[0:36] == instance.uuid
        assert timestamp >= t1
        assert timestamp <= t2

    loop.run_until_complete(_async())

    os.kill(os.getpid(), signal.SIGINT)
    loop.run_until_complete(future)


def test_protobuf_base_no_proto_class(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/dummy_protobuf_service.py', monkeypatch)

    instance = services.get('test_dummy_protobuf')

    async def _async() -> None:
        data = Person()
        data.name = 'John Doe'
        data.id = '12'
        protobuf_message = await instance.message_protocol.build_message(instance, 'topic', data)
        result, message_uuid, timestamp = await instance.message_protocol.parse_message(protobuf_message)
        assert type(result.get('data')) is not Person
        assert type(result.get('data')) is bytes
        assert result.get('data') != data
        assert result.get('data') == b'\n\x0212"\x08John Doe'

    loop.run_until_complete(_async())

    os.kill(os.getpid(), signal.SIGINT)
    loop.run_until_complete(future)


def test_protobuf_base_bad_proto_class(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/dummy_protobuf_service.py', monkeypatch)

    instance = services.get('test_dummy_protobuf')

    async def _async() -> None:
        data = Person()
        data.name = 'John Doe'
        data.id = '12'
        json_message = await instance.message_protocol.build_message(instance, 'topic', data)
        await instance.message_protocol.parse_message(json_message, str)

    with pytest.raises(AttributeError):
        loop.run_until_complete(_async())

    os.kill(os.getpid(), signal.SIGINT)
    loop.run_until_complete(future)


def test_protobuf_validation_no_proto_class(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/dummy_protobuf_service.py', monkeypatch)

    instance = services.get('test_dummy_protobuf')

    async def _async() -> None:
        instance.message_protocol.validate()

    with pytest.raises(Exception):
        loop.run_until_complete(_async())

    os.kill(os.getpid(), signal.SIGINT)
    loop.run_until_complete(future)


def test_protobuf_validation_bad_proto_class(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service('tests/services/dummy_protobuf_service.py', monkeypatch)

    instance = services.get('test_dummy_protobuf')

    async def _async() -> None:
        instance.message_protocol.validate(proto_class=str)

    with pytest.raises(Exception):
        loop.run_until_complete(_async())

    os.kill(os.getpid(), signal.SIGINT)
    loop.run_until_complete(future)


def test_protobuf_object_validation_function(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service(
        'tests/services/dummy_protobuf_service.py', monkeypatch)

    instance = services.get('test_dummy_protobuf')

    def test_validator(person: Person) -> None:
        validate_field_regex(person.name, r'^[a-zA-Z ]+$')

    async def _async() -> None:
        data = Person()
        data.name = 'John Doe'
        data.id = '12'
        protobuf_message = await instance.message_protocol.build_message(
            instance, 'topic', data)
        await instance.message_protocol.parse_message(
            protobuf_message, Person, test_validator)

    loop.run_until_complete(_async())

    os.kill(os.getpid(), signal.SIGINT)
    loop.run_until_complete(future)


def test_protobuf_object_static_validation_function(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service(
        'tests/services/dummy_protobuf_service.py', monkeypatch)

    instance = services.get('test_dummy_protobuf')

    def test_static_validator(person: Person) -> None:
        validate_field_regex(person.name, r'^[a-zA-Z ]+$')

    async def _async() -> None:
        data = Person()
        data.name = 'John Doe'
        data.id = '12'
        protobuf_message = await instance.message_protocol.build_message(
            instance, 'topic', data)

        await instance.message_protocol.parse_message(
            protobuf_message, Person, test_static_validator)

    loop.run_until_complete(_async())

    os.kill(os.getpid(), signal.SIGINT)
    loop.run_until_complete(future)


def test_protobuf_object_validation_function_fail(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service(
        'tests/services/dummy_protobuf_service.py', monkeypatch)

    instance = services.get('test_dummy_protobuf')

    def test_validator(person: Person) -> None:
        validate_field_regex(person.name, r'^(#?[a-fA-F0-9]{6}|)$')

    async def _async() -> None:
        data = Person()
        data.name = 'John Doe'
        data.id = '12'
        protobuf_message = await instance.message_protocol.build_message(
            instance, 'topic', data)
        await instance.message_protocol.parse_message(
            protobuf_message, Person, test_validator)

    with pytest.raises(RegexMissmatchException):
        loop.run_until_complete(_async())

    os.kill(os.getpid(), signal.SIGINT)
    loop.run_until_complete(future)


def test_protobuf_object_static_validation_function_fail(monkeypatch: Any, capsys: Any, loop: Any) -> None:
    services, future = start_service(
        'tests/services/dummy_protobuf_service.py', monkeypatch)

    instance = services.get('test_dummy_protobuf')

    def test_static_validator(person: Person) -> None:
        validate_field_regex(person.name, r'^(#?[a-fA-F0-9]{6}|)$')

    async def _async() -> None:
        data = Person()
        data.name = 'John Doe'
        data.id = '12'
        protobuf_message = await instance.message_protocol.build_message(
            instance, 'topic', data)

        await instance.message_protocol.parse_message(
            protobuf_message, Person, test_static_validator)

    with pytest.raises(RegexMissmatchException):
        loop.run_until_complete(_async())

    os.kill(os.getpid(), signal.SIGINT)
    loop.run_until_complete(future)
