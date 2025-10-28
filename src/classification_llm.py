import os
import re
import sys
from openai import AzureOpenAI
import argparse
import csv

client = AzureOpenAI(
    azure_endpoint = "ENDPOINT"
    api_version = "DATE",
    api_key = "API_KEY"
)


def get_instruction (item, brand_information, cbrand, pbrand):
    '''商品の対象・対象外分類のためのプロンプトを返す'''
    
    system_role = f"""
    あなたは優秀なE-commerceの製品分析者です。
    """
    prompt = f"""
    今、'{cbrand}'というメーカーの'{pbrand}'というプロダクトブランドについて調査しています。
    「#入力」が示す、ある製品の情報（タイトルやGTINコードなど）を見て、'{pbrand}'の製品情報であるかどうかを判断してください。'{cbrand}'および'{pbrand}'については、下の「#メーカーである'{cbrand}'とプロダクトブランドである'{pbrand}'について」を参照してください。
    以下の点に注意してください。
    - 「#入力」に示される情報に、'{pbrand}'の文字列が含まれるときは'{pbrand}'の製品情報である可能性が高いですが、文字列が何らかのサブストリングや全く関係のない文脈で用いられているときは製品情報ではありません。
    
    - メーカーである'{cbrand}'、プロダクトブランドである'{pbrand}'にはスペルバリエーション等があるので気をつけてください。
    - 競合のブランド等の行を抽出しないように注意してください。
    - メーカーには複数のプロダクトブランドがあります。同じメーカーの違うプロダクトブランドの行を抽出しないように注意してください。    
    - '{pbrand}'がどういう種類の製品であるか（例えば洗剤なのか化粧品なのか、など）、に着目して、誤った種類の製品を抽出しないようにしてください。
    - '{pbrand}'の製品と一緒に他の製品がセットになっている場合もありますが、'{pbrand}'が含まれるならTRUEとしてください。    
    - '{pbrand}'の製品情報であると判断すれば出力は、”TRUE”を、そうでなければ"FALSE"を出力してください。
    - ストーブなどのプロダクトブランド'{pbrand}'に関しては、「Sengoku Aladdin（センゴクアラジン）」も同じブランドとして扱ってください。
    - 他に余計な情報は出力しなくて良いです。
    - 与えられる製品の情報「#入力」は、GTINコード（あれば）、製品名（あれば）、商品名、メーカー名、商品が属するジャンル名、さらに詳細なジャンル名、となっています。
    
    #メーカーである'{cbrand}'とプロダクトブランドである'{pbrand}'について
    {brand_information}

    #入力
    {item}

    #出力
    """

    return system_role,prompt


def get_brand_information_prompt(cbrand, pbrand, memo):
    '''ブランド情報調査エージェント用のプロンプトを返す'''
    
    system_role = f"""
    あなたは優秀なマーケットアナリストです。
    """
    prompt = f"""
    今、'{cbrand}'というメーカーの'{pbrand}'というプロダクトブランドについて調査しています。
    '{cbrand}'と'{pbrand}'について以下のことを調べてください。ただし、「#追加情報」に情報があれば、その情報を加味して調査してください。
    - カンパニーブランドである'{cbrand}'が提供する製品の種類（コスメティクス、洗濯洗剤、台所洗剤、シャンプーなど）
    - カンパニーブランドである'{cbrand}'が提供する製品のプロダクトブランド
    - カンパニーブランドである'{cbrand}'の競合カンパニーブランド
    - プロダクトブランドである'{pbrand}'の競合の他社ブランド

#追加情報
    {memo}
    
#出力
"""
    return system_role,prompt


def check_brand_information(cbrand, pbrand, analysis):
    '''ブランド情報調査エージェント用のプロンプトを返す'''
    
    system_role = f"""
あなたは優秀なマーケットアナリストです。
    """
    prompt = f"""
今、'{cbrand}'というメーカーの'{pbrand}'というプロダクトブランドについて調査しています。次に与える調査結果についてレビューしてください。
情報が正しければ、与えられる情報をそのまま編集せずに出力してください。
情報が誤っているもしくは不足しているならフォーマットを変更せずに情報を修正・追加してください。

#調査結果入力
{analysis}
    
#出力
"""
    return system_role,prompt



def call_gpt(prompt, system_role):
    ''' Function to call GPT model with a prompt '''
    
    chat_completion = client.chat.completions.create(
        #model='rit-gpt', #GPT4o
        #model='gpt-4o-mini',
        model='gpt-4.1-mini',
        messages=[
            {"role": "user", "content": prompt},
            #{"role": "system", "content": ""},
            {"role": "system", "content": system_role},            
        ]
    )
    response = chat_completion.choices[0].message.content
    return response


def query_llm(model, prompt, system_role):
    '''
    
    '''
    completion = openai.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt},
            {"role": "system", "content": system_role},
        ]
    )
    # print the completion
    #print(completion.choices[0].message.content)
    response = completion.choices[0].message.content
    return response


def main (tgt_file, cbrand, pbrand, memo):

    with open(tgt_file, newline='') as f:

        # get cbrand/pbrand information through LLM
        system_role, instruction = get_brand_information_prompt(cbrand, pbrand, memo)
        brand_information = call_gpt(system_role, instruction)

        print(f'{brand_information}',file=sys.stderr)
        cnt = 0
        while (1):
            if cnt == 1: #### TEST 10/09 ####
                break
            system_role, instruction = check_brand_information(cbrand, pbrand, brand_information)
            new_brand_information = call_gpt(system_role, instruction)
            if brand_information == new_brand_information:
                break
            print(f'{brand_information}',file=sys.stderr)
            cnt += 1
        
        items = []
        for row in csv.reader(f, delimiter='\t'):
            orig_line = "\t".join(row)
            new = []
            new_line = get_newline(row) # 00_inclusionとexclusionをマージした時の通し番号と正解部分を除く
            res = []
            
            system_role, instruction = get_instruction(new_line, brand_information, cbrand, pbrand)            
            
            response = call_gpt(system_role, instruction)
            print(f'{response}\t{orig_line}')
            print(f'{response}\t{orig_line}',file=sys.stderr)

            
def get_newline(row):

    gtin = row[2]
    ptitle = row[3]
    ititle = row[4]
    maker = row[5]
    filterset_code = row[6]
    g1_id = row[7]
    g1_name = row[8]
    g2_id = row[9]
    g2_name = row[10]    

    newline = f"""
GTIN: {gtin}
製品タイトル: {ptitle}
商品タイトル: {ititle}
メーカー名: {maker}
ジャンル: {g1_name} >> {g2_name}
"""
    return newline

    
if __name__ == "__main__":

  parser = argparse.ArgumentParser()
  parser.add_argument('-f', '--file', required=True)    # Target Data file
  parser.add_argument('-c', '--cbrand', required=True)    # corporate brand
  parser.add_argument('-p', '--pbrand', required=True)    # product brand
  parser.add_argument('-m', '--memo', required=True)    # product brand  
  args = parser.parse_args()

  tgt_file = args.file
  cbrand = args.cbrand
  pbrand = args.pbrand
  memo = args.memo
  
  main(tgt_file, cbrand, pbrand, memo) # main
    

