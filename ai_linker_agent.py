# 개별 python 파일 tool 을 기반으로 작동하는 에이전트 코드
from tools.utils.SystemUtils import PrivacyUtils
# from tools.tool_generator import ToolGenerationPipeline
from tools.openai_generator import OpenAISpecGenerator
from tools.gemini_generator import GeminiCodeGenerator
from tools.claude_generator import ClaudeCodeGenerator
from tools.openai_hybrid_generator import OpenAIHybridCodeGenerator
from tools.tool_loader import ToolLoader
import json
import os
from tools.utils.log_util import LoggingMixin 


# self._log 는 'print'와 logging 을 포함하는 함수이다.
# logging.을 통해 외부 api response 로 과정을 보여준다

class AIAgent(LoggingMixin):
    def __init__(self, user_id: str, rag_system, user_database, _client):
        self.rag_system = rag_system
        self.user_id = user_id
        self.USER_DB = user_database
        self.user = self.USER_DB.get(user_id, {"user_id": user_id})
        self.client = _client
        self._reload_tools()

        self.spec_generator = OpenAISpecGenerator()
        # 코드 생성에 제미니 이용
        # self.code_generator = GeminiCodeGenerator()
        # 코드 생성에 Claude 이용
        # self.code_generator = ClaudeCodeGenerator()
        # 코드 생성에 OpenAI 이용
        self.code_generator = OpenAIHybridCodeGenerator()


    # Tool 을 다시 불러오는 함수
    def _reload_tools(self):
        print("\n[AI Agent] 도구 목록을 새로고침합니다...")

        self.tool_loader = ToolLoader(
            rag_system=self.rag_system,
            user_database=self.USER_DB,
            tool_directory="tools"
        )

        self.tools = self.tool_loader.tools
        self.available_tools = {tool.name: tool.execute for tool in self.tools}
        self.api_tools = [
            {"type": "function", "function": {
                "name": tool.name, "description": tool.description, "parameters": tool.parameters
            }} for tool in self.tools
        ]

        print(f"[AI Agent] 현재 사용 가능한 도구: {[tool.name for tool in self.tools]}")


    # GateKeeper Filter 함수
    # LLM이 사람을 돕도록 System prompt 가 있어 서비스 외 질문에도 답변을 해버린다
    # 이러한 현상을 해결하기 위해 맨 앞에서 서비스 의도 질문인지를 분류해버림
    def _is_query_in_scope(self, query: str) -> bool:
        self._log("   [Gatekeeper] 사용자 질문의 의도를 분류합니다...")

        # 의도 분류만을 위한 매우 구체적이고 단순한 프롬프트
        system_prompt = """
            당신은 사용자 질문의 핵심 의도가 '대한민국의 행정 또는 금융 신청 업무'와 관련 있는지 판단하는 분류 전문가입니다.
            사용자의 궁극적인 목표가 대출, 지원금, 계좌 개설, 서류 발급 등과 관련 있다면 'YES'입니다.

            **판단 예시:**
            - 질문: "IT 스타트업을 차릴 건데, 사업자금 대출 알려줘." -> YES
            - 질문: "가게 운영자금이 부족해요." -> YES
            - 질문: "청년도약계좌 만들고 싶어요." -> YES
            - 질문: "오늘 날씨 어때?" -> NO
            - 질문: "낚시하는 법 알려줘" -> NO

            다른 어떤 설명도 하지 말고, 오직 'YES' 또는 'NO'로만 대답하세요.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o", # 또는 더 저렴한 gpt-3.5-turbo 사용 가능
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                max_tokens=2, # 답변을 'YES' 또는 'NO'로 제한
                temperature=0.0
            )
            decision = response.choices[0].message.content.strip().upper()
            print(f"   [Gatekeeper] 판단 결과: {decision}")
            return decision == "YES"
        except Exception as e:
            print(f"   [Gatekeeper] 의도 분류 중 오류 발생: {e}")
            return False # 오류 발생 시 보수적으로 접근하여 거절


    # 도구 코드가 실패한 경우 문제 분석
    def _analyze_tool_loading_failure(self, tool_spec: dict, tool_directory: str = "tools") -> str:
        """[신규] 로드에 실패한 도구 코드의 문제점을 분석합니다."""
        tool_name = tool_spec.get("name")
        filepath = os.path.join(tool_directory, f"{tool_name}_tool.py")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                faulty_code = f.read()
        except FileNotFoundError:
            return "파일을 찾을 수 없습니다."

        prompt = f"다음 파이썬 코드는 'ToolBase'를 상속받아야 하지만, 인스턴스화에 실패했습니다. 코드의 문제점을 한 문장으로 요약해주세요.\n\n{faulty_code}"
        response = self.client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        return response.choices[0].message.content


    # 실제 에이전트 실행
    def run(self, initial_query: str) -> dict:
        self.execution_log = []

        print(f"tool_loader : {self.tool_loader}")
        print(f"tools : {self.tools}")
        print(f"정의된 Tool들 : {self.api_tools}")
        print(f"사용가능 Tool들 : {self.available_tools}")
        self._log(f"[Alarm]{'#'*2} AI Agent Process Start (Query: '{initial_query}') {'#'*2}")

        # LLM 에 민감정보를 던지지 않기 위해 임의의 id를 내부 Database 에서 조회한다
        contextual_query = f"""
            [사용자 ID]
            {self.user.get('user_id', 'N/A')}

            [사용자 요청 사항]
            {initial_query}
        """

        # GateKeeper 에 의해 질문의 정상 여부(서비스 목적에 맞는지) 확인
        if not self._is_query_in_scope(initial_query):
            refusal_message = "죄송합니다. 저는 대한민국의 행정 및 금융 신청을 돕기 위해 설계된 전문 AI 에이전트입니다. 문의하신 내용에 대해서는 답변을 드리기 어렵습니다. '소상공인 대출'이나 '청년도약계좌' 등 도움이 필요한 신청 업무가 있으시다면 말씀해주세요."
            self._log(f"[AI-Linker 최종 답변] {refusal_message}")
            self._log(f"[Alarm]{'#'*2} AI Agent Process Finished (Out of Scope) {'#'*2}")
            # return # 프로세스 즉시 종료
            return {
                "final_result": {
                    "status": "rejected",
                    "message": refusal_message
                },
                "execution_log": self.execution_log
            }


        final_result = {"status": "error", "message": "에이전트가 작업을 완료하지 못했습니다."}

        contextual_query = f"""
            [사용자 ID]
            {self.user.get('user_id', 'N/A')}
            [사용자 요청 사항]
            {initial_query}
        """


        # --- 이 아래는 '문지기'를 통과한 경우에만 실행됩니다 ---
        messages = [
            {"role": "system",
             "content": 
"""
                ### 역할 정의 ###
                당신은 'AI-Linker'입니다. 당신의 유일한 임무는 '대한민국의 행정 및 금융 신청 업무'를 자동화하여 사용자를 돕는 것입니다.
                당신에게 전달된 모든 사용자 요청은 이미 관련성 검사를 통과했습니다. 당신은 질문의 의도를 의심할 필요 없이, 오직 아래의 업무 수행 계획에 따라 목표를 완수하는 데만 집중하세요.
                당신은 오직 '사용자 ID'를 통해서만 사용자를 식별하며, 절대 실제 개인정보를 묻거나 다루지 않습니다.
                도구를 사용할 때는, 반드시 [사용자 ID] 컨텍스트로 제공된 값을 그대로 사용해야 합니다.
                절대로 임의의 ID나 예시 값을 만들어서 사용하면 안 됩니다.


                ### **[매우 중요한 업무 수행 계획 (SOP)]** ###
                당신은 반드시 다음의 논리적 순서에 따라 단계별로 계획을 세우고 도구를 사용해야 합니다.

                **0. 지식 동기화:**
               - 가장 먼저, `synchronize_knowledge_base` 도구를 사용해 `latest_policies.json` 파일과 당신의 지식을 동기화하여 최신 상태를 유지합니다.

                **1. 정보 검색 단계:**
                - 가장 먼저, 사용자의 질문 의도를 파악하여 `search_knowledge_base` 도구를 사용해 관련 정책 정보를 검색합니다.
                - 만약 검색 결과가 "관련 정보를 찾지 못했습니다" 라면, 더 이상 다른 도구를 사용하지 말고 사용자에게 이 사실을 알리고 프로세스를 종료합니다.

                **2. 사업자 상태 확인:**
                - 먼저, `사용자 ID`를 `verify_business_registration` 도구에 전달하여 국세청 상태를 확인합니다.
                - 상태가 정상이 아니면 프로세스를 중단합니다.

                **3. 서류 수집 및 검증 단계:**
                - 정보 검색에 성공했다면, 결과에 포함된 **`metadata`의 `required_docs` 리스트**를 확인합니다.
                - 리스트에 있는 **모든 서류에 대해**, `fetch_document_from_mcp` 도구를 **하나씩 순서대로 호출**하여 서류를 가져옵니다.
                - 각 서류를 가져온 직후, 즉시 `validate_document` 도구를 사용하여 해당 서류가 유효한지 검증합니다.

                **4. 최종 제출 단계:**
                - 모든 서류의 수집 및 검증이 성공적으로 완료되었다면, 확보한 모든 `doc_token`들을 모아 `submit_application` 도구를 호출하여 최종 제출을 완료합니다.

                **5. [매우 중요] 작업 완료:**
                - **'submit_application' 도구 호출이 성공적으로 끝난 직후**, 당신의 다음 행동은 **반드시 `finish_task` 도구를 호출**하여 최종 요약 메시지와 함께 작업을 종료해야 합니다.
                - 'submit_application'의 결과(예: 신청ID 등)를 'finish_task'의 'summary' 파라미터에 포함하여 사용자에게 최종 보고하고 작업을 종료해야 합니다.

                ### **[매우 중요한 출력 형식 규칙]** ###
                - 당신이 도구를 사용해야 한다고 판단했을 때, 다른 자연어 설명은 일절 포함하지 마십시오.
                - 반드시 `tool_calls` JSON 객체 형식으로만 응답해야 합니다.
                """
            },
            # {"role": "user", "content": initial_query}
            {"role": "user", "content": contextual_query} # user_id 로 되어있는 부분을 이용하도록 유도
        ]

        # json 대신 dict 반환
        # final_result_message = json.dumps({"status": "error", "message": "에이전트가 작업을 완료하지 못했습니다."})
        final_result = {"status": "error", "message": "에이전트가 작업을 완료하지 못했습니다."}


        for i in range(7): # 최대 7단계 실행
            self._log(f". [STEP] Agent Step {i+1}")

            response = self.client.chat.completions.create(
                model="gpt-4o", messages=messages, tools=self.api_tools, tool_choice="auto"
            )
            response_message = response.choices[0].message
            messages.append(response_message)

            print(f"responseMsg : {response_message}")

            if not response_message.tool_calls:
                # [개선] AI가 작업을 완료하지 못했다고 판단되면, 자기 개선 로직 실행
                self._log("  [Thought] 현재 도구로는 이 요청을 완료할 수 없습니다. 새로운 도구가 필요한지 확인합니다.")

                # 1. OpenAI가 명세서 생성
                existing_tool_names = [t.name for t in self.tools]
                new_tool_spec = self.spec_generator.generate_spec(initial_query, existing_tool_names)

                if new_tool_spec:
                    print(f". [AI Agent] 필요한 새 도구의 명세서를 생성했습니다. (new_tool_spec : {new_tool_spec})")

                    # 2. OpenAI기반 하이브리드(rule기반 + LLM기반) 명세서 기반으로 코드 생성 및 등록
                    success = self.code_generator.create_and_register_tool(new_tool_spec)
                else:
                    self._log("  [AI Agent] 추가 도구가 필요 없다고 판단. 최종 답변을 출력합니다.")
                    self._log(f"   [Final Answer] {response_message.content}")

                if success:
                    self._reload_tools()
                    self._log("  [AI Agent] 새 도구를 장착했습니다. 처음부터 작업을 다시 시도합니다.")
                    continue
                else:
                    self._log("  [AI Agent] 새 도구 제작에 실패하여, 작업을 중단합니다.")

                # return
                return {"final_result": final_result, "execution_log": self.execution_log}


            # 기존 Tool Calling 로직
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # AI가 '작업 완료' 신호를 보낸 경우 -> 완전 종료
                if function_name == "finish_task":
                    summary = function_args.get('summary', '작업이 완료되었습니다.')
                    self._log(f"   [Thought] 모든 작업이 완료되었다고 판단했습니다.")
                    self._log(f"   [Final Answer] {summary}")

                    # JSON 대신 순수한 dict 반환
                    # final_result_message = json.dumps({"status": "success", "message": summary})
                    final_result = {"status": "success", "message": summary}

                    # 루프를 탈출하기 위해 플래그 설정
                    should_break_loop = True
                    break

                function_to_call = self.available_tools[function_name]

                # parameter 를 넘기지 않는 경우 해결
                # 하드 코딩하는 것이 최선의 방안인가?
                if not function_args :
                    tool_output = function_to_call(user=self.user)
                else :
                    tool_output = function_to_call(**function_args)

                messages.append({"tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": tool_output})
            
            if 'should_break_loop' in locals() and should_break_loop:
                break

        print(f"[Alarm]{'#'*2} AI Agent Process Finished {'#'*2}")
        return {"final_result": final_result, "execution_log": self.execution_log}