from unittest import mock

from src.emulator import Emulator, GAME_START_ADDRESS


class TestIndividualOpcodes:
    def setup_method(self):
        self.emulator = Emulator()

    def test_opcode_return_from_subroutine(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."
        assert len(self.emulator.stack) == 0, "Stack starting out non-empty."

        self.emulator.opcode_return_from_subroutine(bytes.fromhex("00EE"))
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Returning from a subroutine when not in one messed up the program counter."
        assert len(self.emulator.stack) == 0, "Stack got into a weird state when trying to return from a subroutine when not in one."

        self.emulator.stack = [2000, 3000]
        self.emulator.opcode_return_from_subroutine(bytes.fromhex("00EE"))
        assert self.emulator.program_counter == 3000, "Program counter set to wrong value when returning from a subroutine."
        assert len(self.emulator.stack) == 1, "Stack entries incorrect after returning from a subroutine."

        self.emulator.opcode_return_from_subroutine(bytes.fromhex("00EE"))
        assert self.emulator.program_counter == 2000, "Program counter set to wrong value when returning from a subroutine."
        assert len(self.emulator.stack) == 0, "Stack entries incorrect after returning from a subroutine."

    def test_opcode_goto(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."

        self.emulator.opcode_goto(bytes.fromhex("14e5"))
        assert self.emulator.program_counter == int("4e5", 16), "Program counter incorrect after jump opcode."

    def test_opcode_call_subroutine(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."
        assert len(self.emulator.stack) == 0, "Stack starting out non-empty."

        self.emulator.opcode_call_subroutine(bytes.fromhex("2578"))
        assert self.emulator.program_counter == int("578", 16), "Program counter incorrect after subroutine call."
        assert len(self.emulator.stack) == 1 and self.emulator.stack[0] == GAME_START_ADDRESS, "Previous program counter not added to the stack."

        self.emulator.opcode_call_subroutine(bytes.fromhex("2a23"))
        assert self.emulator.program_counter == int("a23", 16), "Program counter incorrect after subroutine call."
        assert len(self.emulator.stack) == 2 and self.emulator.stack[1] == int("578", 16), "Previous program counter not added to the stack."
        assert len(self.emulator.stack) == 2 and self.emulator.stack[0] == GAME_START_ADDRESS, "Earlier stack value was modified."

    def test_opcode_if_equal(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."
        assert self.emulator.registers[6] == 0, "Register starting at an unexpected value."

        self.emulator.opcode_if_equal(bytes.fromhex("3698"))
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter was changed despite register value not matching."

        self.emulator.registers[6] = int("98", 16)
        self.emulator.opcode_if_equal(bytes.fromhex("3698"))
        assert self.emulator.program_counter == GAME_START_ADDRESS + 2, "Next instruction was not skipped when it should have been."

    def test_opcode_if_not_equal(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."

        self.emulator.registers[6] = int("98", 16)
        self.emulator.opcode_if_not_equal(bytes.fromhex("3698"))
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter was changed despite register value matching."

        self.emulator.registers[6] = int("ff", 16)
        self.emulator.opcode_if_not_equal(bytes.fromhex("3698"))
        assert self.emulator.program_counter == GAME_START_ADDRESS + 2, "Next instruction was not skipped when it should have been."

    def test_opcode_if_register_equal(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."

        self.emulator.registers[10] = int("11", 16)
        self.emulator.registers[4] = int("12", 16)
        self.emulator.opcode_if_register_equal(bytes.fromhex("5a40"))
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter was changed despite register value matching."

        self.emulator.registers[10] = int("40", 16)
        self.emulator.registers[4] = int("40", 16)
        self.emulator.opcode_if_register_equal(bytes.fromhex("5a40"))
        assert self.emulator.program_counter == GAME_START_ADDRESS + 2, "Next instruction was not skipped when it should have been."

    def test_opcode_set_register_value(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.opcode_set_register_value(bytes.fromhex("6133"))
        for index, register in enumerate(self.emulator.registers):
            if index == 1:
                assert register == int("33", 16), "Register not set to correct value."
            else:
                assert register == 0, "Different register than target had its value modified."

    def test_opcode_add_value(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.registers[11] = 10
        self.emulator.opcode_add_value(bytes.fromhex("7b05"))
        for index, register in enumerate(self.emulator.registers):
            if index == 11:
                assert register == 15, "Register addition failed."
            else:
                assert register == 0, "Different register than target had its value modified."

        self.emulator.opcode_add_value(bytes.fromhex("7bfa"))
        assert self.emulator.registers[11] == 9, "Register addition overflow did not work as expected."
        assert self.emulator.registers[15] == 0, "Carry bit was set when it should not be modified by this instruction."

    def test_opcode_set_register_value_other_register(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.registers[8] = 47
        self.emulator.opcode_set_register_value_other_register(bytes.fromhex("8480"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4 or index == 8:
                assert register == 47, "Register not set to correct value."
            else:
                assert register == 0, "Different register than target had its value modified."

    def test_opcode_set_register_bitwise_or(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.registers[4] = 170
        self.emulator.registers[8] = 85
        self.emulator.opcode_set_register_bitwise_or(bytes.fromhex("8481"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 255, "Register not set to correct value."
            elif index == 8:
                assert register == 85, "Second register value was modified when it should not have been."
            else:
                assert register == 0, "Different register than target had its value modified."

    def test_opcode_set_register_bitwise_and(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.registers[4] = 204
        self.emulator.registers[8] = 170
        self.emulator.opcode_set_register_bitwise_and(bytes.fromhex("8482"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 136, "Register not set to correct value."
            elif index == 8:
                assert register == 170, "Second register value was modified when it should not have been."
            else:
                assert register == 0, "Different register than target had its value modified."

    def test_opcode_set_register_bitwise_xor(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.registers[4] = 204
        self.emulator.registers[8] = 170
        self.emulator.opcode_set_register_bitwise_xor(bytes.fromhex("8483"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 102, "Register not set to correct value."
            elif index == 8:
                assert register == 170, "Second register value was modified when it should not have been."
            else:
                assert register == 0, "Different register than target had its value modified."


class TestOpcodeRouting:
    @classmethod
    def setup_class(cls):
        cls.emulator = Emulator()

    def run_opcode(self, opcode: bytes, bad_opcode: bytes, mock_method: mock.patch.object):
        self.emulator.run_opcode(bad_opcode)
        mock_method.assert_not_called()

        self.emulator.run_opcode(opcode)
        mock_method.assert_called_with(opcode)

    @mock.patch.object(Emulator, "opcode_goto")
    def test_goto(self, mock_method):
        opcode = bytes.fromhex("132a")
        bad_opcode = bytes.fromhex("332a")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_call_subroutine")
    def test_call_subroutine(self, mock_method):
        opcode = bytes.fromhex("232a")
        bad_opcode = bytes.fromhex("332a")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_if_equal")
    def test_if_equal(self, mock_method):
        opcode = bytes.fromhex("332a")
        bad_opcode = bytes.fromhex("132a")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_if_not_equal")
    def test_if_not_equal(self, mock_method):
        opcode = bytes.fromhex("432a")
        bad_opcode = bytes.fromhex("132a")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_if_register_equal")
    def test_if_register_equal(self, mock_method):
        opcode = bytes.fromhex("5320")
        bad_opcode = bytes.fromhex("5321")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_set_register_value")
    def test_set_register_value(self, mock_method):
        opcode = bytes.fromhex("6133")
        bad_opcode = bytes.fromhex("5321")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_add_value")
    def test_add_value(self, mock_method):
        opcode = bytes.fromhex("7433")
        bad_opcode = bytes.fromhex("6133")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_return_from_subroutine")
    def test_return_from_subroutine(self, mock_method):
        opcode = bytes.fromhex("00EE")
        bad_opcode = bytes.fromhex("7433")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_set_register_value_other_register")
    def test_set_register_value_other_register(self, mock_method):
        opcode = bytes.fromhex("8480")
        bad_opcode = bytes.fromhex("00EE")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_set_register_bitwise_or")
    def test_set_register_bitwise_or(self, mock_method):
        opcode = bytes.fromhex("8481")
        bad_opcode = bytes.fromhex("8480")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_set_register_bitwise_and")
    def test_set_register_bitwise_and(self, mock_method):
        opcode = bytes.fromhex("8482")
        bad_opcode = bytes.fromhex("8481")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_set_register_bitwise_xor")
    def test_set_register_bitwise_xor(self, mock_method):
        opcode = bytes.fromhex("8483")
        bad_opcode = bytes.fromhex("8482")
        self.run_opcode(opcode, bad_opcode, mock_method)
