import os
import sys
import json
from Mono_py10 import Lexer, Normalizer, load_rule, create_rule_template
import traceback

dir_path = os.path.dirname(os.path.abspath(__file__))
running_path = os.getcwd()
forgefile_path = os.path.dirname(dir_path)
debug = False
debug_ir = False

class ForgeFile:
    def __init__(self,_args):
        self.variable = {}
        self.args = _args[1:]
        self.ir = []
        self.pc = 0
        self.mapping_function = {
            "shell_cmd":self.shell_cmd,
            "create_func":self.create_func,
            "call_func":self.call_func,
            "run_python":self.run_python,
            "let_cmd":self.let_cmd,
            "evel_cmd":self.evel_cmd,
            "not_let_cmd":self.not_let_cmd,
        }
        self.func = {}

    def calc_var_string(self, text):
        parse = text.split()
        # Rebuild the list: replace if it starts with '$$' and exists in self.variable, otherwise keep it
        updated_parse = [
            str(self.variable[p[2:]]) if p[0:2] == "$$" and p[2:] in self.variable else p
            for p in parse
        ]
        return " ".join(updated_parse)

    def evel_cmd(self,data):
        if len(data) < 2:
            raise Exception("Bad variable")
        self.variable[data[0]["value"]] = eval(data[1]["value"],self.variable)

    def let_cmd(self,data):
        if len(data) < 2:
            raise Exception("Bad variable")
        self.variable[data[0]["value"]] = self.calc_var_string(data[1]["value"])

    def not_let_cmd(self,data):
        if len(data) < 2:
            raise Exception("Bad variable")
        if not data[0]["value"] in self.variable:
            self.variable[data[0]["value"]] = self.calc_var_string(data[1]["value"])

    def run_python(self,data):
        exec(data[0]["value"],self.variable)

    def create_func(self,data):
        if len(data) < 2:
            raise Exception("Bad create Function.")
        func_name = data[0]["value"]
        self.func[func_name] = {"code":data[1]}

    def call_func(self,data):
        if len(data) == 0:
            raise Exception("bad call function.")
        func_name = data[0]["value"]
        
        if not func_name in self.func:
            raise Exception(f"Not {func_name} in function list.")
        _function = self.func[func_name]

        ff = ForgeFile(self.args)
        ff.variable = self.variable
        ff.ir = _function["code"]
        ff.running_ir()
        self.variable = ff.variable

    def shell_cmd(self, data):
        raw_command = data[0]["value"]
        print(raw_command)
        
        # 1. แปลงตัวแปร $$ ก่อนเป็นอันดับแรกด้วยฟังก์ชันที่เราแก้กันไว้
        processed_command = self.calc_var_string(raw_command)
        
        # 2. ค่อยเอาคำสั่งที่แปลงตัวแปรแล้วมาตัดแบ่งเพื่อเช็คคำว่า "try"
        parse = processed_command.split(" ")
        
        # เช็คว่าขึ้นต้นด้วย try หรือไม่ (ใช้ .strip() ช่วยเผื่อมีช่องว่างหลุดมา)
        if parse[0].strip() in ["try", "_try"]:
            try:
                # รันคำสั่งทั้งหมดที่อยู่ต่อจากคำว่า try โดยประกอบร่างกลับคืน
                final_cmd = " ".join(parse[1:])
                os.system(final_cmd)
            except Exception as e:
                print(f"[TRY] {e}")
        else:
            # ถ้ารันปกติก็นำคำสั่งที่แปลงตัวแปรเสร็จแล้วไปใช้ได้เลย
            os.system(processed_command)

    def set_variable_cmd(self,_args):
        for cmd in _args:
            parse = cmd.split("=")
            if len(parse) < 2:
                continue
            self.variable[parse[0]] = parse[1]

    def look(self):
        if self.pc < len(self.ir):
            return self.ir[self.pc]
        return None
    
    def next(self,k=1):
        if self.pc+k <= len(self.ir):
            self.pc += k

    def peek(self,k=1):
        if self.pc+k < len(self.ir):
            return self.ir[self.pc+k]
        return None

    def running_ir(self):
        while self.look() != None:
            try:
                node = self.look()
                if node["action"] in self.mapping_function:
                    func = self.mapping_function[node["action"]]
                    func(node["data"])
            except Exception as e:
                print(f"[ERROR] {e} in {node['line']+1}:{node['col']+1}")
                sys.exit(1)
                if debug:
                    traceback.print_exc()
            self.next()

    def running_cmd(self):
        if len(self.args) < 1:
            sys.exit()
        func_args = [a for a in self.args if len(a.split("=")) <= 1]

        if len(func_args) < 1:
            sys.exit()

        func_name = func_args[0]

        if not func_name in self.func:
            print(f"[ERROR] Not {func_name} in function.")
            sys.exit(1)

        _function = self.func[func_name]
        ff = ForgeFile(self.args)
        ff.variable = self.variable
        ff.ir = _function["code"]
        ff.func = self.func
        ff.running_ir()
        ff.running_cmd()
        self.variable = ff.variable

    def parser_run(self):
        load_rule(os.path.join(forgefile_path,"ForgeFileRule.json"))
        program_path = os.path.join(running_path,"forgefile")
        if not os.path.exists(program_path):
            print("[ERROR] Not forgefile in folder.")
            sys.exit(1)
        try:
            with open(program_path,"r",encoding="utf-8") as f:
                program = f.read()
            tokens = Lexer(program).run()
            ir = Normalizer(tokens).parse()
            if debug_ir:
                print(ir)
            self.ir = ir

        except Exception as e:
            print(f"[ERROR] {e}")
            if debug:
                traceback.print_exception()
            sys.exit(1)

if __name__ == "__main__":
    args = sys.argv
    if debug:
        print(f"[CONFIG] ForgeFile in {forgefile_path}")
        print(f"[CONFIG] Running in {running_path}")
        os.system(f"ls {running_path}")
    forgefile = ForgeFile(args)
    forgefile.parser_run()
    forgefile.set_variable_cmd(args)
    forgefile.running_ir()
    forgefile.running_cmd()