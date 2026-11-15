"""Server-only model routing; Gemini keeps the existing bounded agent contracts."""
import os
from types import SimpleNamespace
from openai import AsyncOpenAI, APIConnectionError, APIStatusError
from app import config  # Load backend and root environment files before selection.


def gemini_key():
    return os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')


def configured():
    return bool(gemini_key() or os.getenv('OPENAI_API_KEY'))


def provider():
    return 'Gemini' if gemini_key() else 'OpenAI'


def model_name():
    return os.getenv('GEMINI_MODEL', 'gemini-3.5-flash') if gemini_key() else os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')


class GeminiClient:
    def __init__(self, **kwargs):
        self.client = AsyncOpenAI(api_key=gemini_key(), base_url='https://generativelanguage.googleapis.com/v1beta/openai/', **kwargs)
        self.responses = self
        self.used_models = []
        self.fallback_used = False

    async def __aenter__(self):
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *args):
        return await self.client.__aexit__(*args)

    async def parse(self, *, instructions, input, text_format, tools=None, max_output_tokens=2200, **_):
        messages = [{'role': 'system', 'content': instructions}]
        items = [{'role': 'user', 'content': input}] if isinstance(input, str) else input
        for item in items:
            if isinstance(item, dict):
                if item.get('type') == 'function_call_output':
                    messages.append({'role': 'tool', 'tool_call_id': item['call_id'], 'content': item['output']})
                else:
                    messages.append(item)
            elif getattr(item, '_message', None) is not None:
                # Preserve the complete provider message, including thought signatures.
                messages.append(item._message)
        schema = text_format.model_json_schema()
        options = dict(model=model_name(), messages=messages, max_tokens=max(4096, max_output_tokens),
                       response_format={'type': 'json_schema', 'json_schema': {'name': text_format.__name__, 'schema': schema}})
        if tools:
            options['tools'] = [{'type': 'function', 'function': {k: v for k, v in t.items() if k in {'name', 'description', 'parameters'}}} for t in tools]
        try:
            response = await self.client.chat.completions.create(**options)
        except (APIConnectionError, APIStatusError) as exc:
            # One same-provider fallback; never retry authentication/schema errors.
            transient = isinstance(exc, APIConnectionError) or exc.status_code in {429, 500, 502, 503, 504}
            fallback = os.getenv('GEMINI_FALLBACK_MODEL', 'gemini-3.5-flash-lite').strip()
            if not transient or not fallback or fallback == options['model']:
                raise
            options['model'] = fallback
            response = await self.client.chat.completions.create(**options)
            self.fallback_used = True
        if options['model'] not in self.used_models:
            self.used_models.append(options['model'])
        message = response.choices[0].message
        if message.refusal:
            raise ValueError('Model declined to produce a report.')
        if message.tool_calls:
            output = [SimpleNamespace(type='function_call', call_id=t.id, name=t.function.name,
                        arguments=t.function.arguments, _message=message.model_dump(exclude_none=True) if i == 0 else None)
                      for i, t in enumerate(message.tool_calls)]
            return SimpleNamespace(output=output, output_parsed=None)
        if response.choices[0].finish_reason != 'stop':
            raise ValueError('Model response incomplete.')
        return SimpleNamespace(output=[], output_parsed=text_format.model_validate_json(message.content or ''))


def llm_client(**kwargs):
    return GeminiClient(**kwargs) if gemini_key() else AsyncOpenAI(**kwargs)
