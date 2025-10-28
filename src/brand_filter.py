#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import re
import json
import argparse
from collections import defaultdict
from typing import Dict, List, Tuple, Set

# UTF-8エンコーディングの設定
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


class JanCodeProcessor:
    """JANコード処理クラス"""
    
    def __init__(self):
        self.opt_debug = False
        
    @staticmethod
    def get_companycode_from_jancode(jancode: str) -> str:
        """
        JANコードから事業者コードを抽出する
        
        Args:
            jancode (str): JANコード
            
        Returns:
            str: 事業者コード
        """
        if re.match(r'^49|^45[0-5]', jancode):
            company_code = jancode[:7]
        else:
            company_code = jancode[:9]
        return company_code


class ProductMasterProcessor:
    """ProductMaster処理クラス"""
    
    def __init__(self):
        self.pm = {}
        self.pm_code = {}
        
    def get_pm_info(self, file_path: str):
        """
        PM情報を読み込む
        
        Args:
            file_path (str): PMファイルのパス
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as fp:
                for line in fp:
                    line = line.strip().lower()
                    parts = line.split('\t')
                    
                    if len(parts) < 9:
                        continue
                        
                    (flag, jan_code, makercd, makername, makernamekana, 
                     makerformalname, brandname, my_makername, my_brands) = parts[:9]
                    
                    jan_processor = JanCodeProcessor()
                    my_makercd = jan_processor.get_companycode_from_jancode(jan_code)
                    my_makercd = "10" + my_makercd
                    
                    makercds = [makercd, my_makercd]
                    
                    for makercd in makercds:
                        # pm_code構造の初期化
                        if makercd not in self.pm_code:
                            self.pm_code[makercd] = {
                                'name': defaultdict(int),
                                'b': defaultdict(int),
                                'mname': defaultdict(int),
                                'mb': defaultdict(int)
                            }
                        
                        self.pm_code[makercd]['name'][makername] += 1
                        self.pm_code[makercd]['b'][brandname] += 1
                        
                        # pm構造の初期化
                        if makercd not in self.pm:
                            self.pm[makercd] = {}
                        if jan_code not in self.pm[makercd]:
                            self.pm[makercd][jan_code] = {
                                'name': None,
                                'b': None,
                                'mname': None,
                                'mb': {}
                            }
                        
                        self.pm[makercd][jan_code]['name'] = makername
                        self.pm[makercd][jan_code]['b'] = brandname
                        
                        if my_makername:
                            self.pm_code[makercd]['mname'][my_makername] += 1
                            self.pm[makercd][jan_code]['mname'] = my_makername
                        
                        if my_brands:
                            for brand in my_brands.split(','):
                                self.pm_code[makercd]['mb'][brand] += 1
                                self.pm[makercd][jan_code]['mb'][brand] = 1
                                
            print(f"size_makercd: {len(self.pm_code)}", file=sys.stderr)
            
        except Exception as e:
            print(f"Error reading PM file: {e}", file=sys.stderr)


class TokenProcessor:
    """トークン処理クラス"""
    
    def __init__(self, debug=False):
        self.debug = debug
        self.htrue = {}
        self.hfalse = {}
        self.hconflict = {}
        
    def read_tokens(self, file_token: str):
        """
        トークンリストの読み込み
        
        Args:
            file_token (str): トークンファイルのパス
        """
        try:
            with open(file_token, 'r', encoding='utf-8') as fp:
                for line in fp:
                    line = line.strip()
                    parts = line.split('\t')
                    
                    if len(parts) < 3:
                        continue
                        
                    true_num, false_num, token = int(parts[0]), int(parts[1]), parts[2]
                    
                    if true_num == 0:
                        self.hfalse[token] = false_num
                    elif false_num == 0:
                        self.htrue[token] = true_num
                    else:
                        self.hconflict[token] = f"{true_num}|{false_num}"
                        
            size_true = len(self.htrue)
            size_false = len(self.hfalse)
            size_conflict = len(self.hconflict)
            
            if self.debug:
                print(f"File:{file_token}\t#tokens_in_True:{size_true}\t"
                      f"#tokens_in_False:{size_false}\t#tokens_in_Conflict:{size_conflict}",
                      file=sys.stderr)
                      
        except Exception as e:
            print(f"Error reading token file: {e}", file=sys.stderr)
            
    def get_tokens_from_title(self, title: str) -> Tuple[Dict, Set, Set, Set]:
        """
        タイトルからトークンを抽出してラベル付け
        
        Args:
            title (str): タイトル文字列
            
        Returns:
            Tuple: (統計情報, TRUE（対象）ワード, FALSE（対象外）ワード, CONFLICTワード)
        """
        hash_info = defaultdict(int)
        true_words = set()
        false_words = set()
        conflict_words = set()
        
        for token in title.split():
            hash_info['length'] += 1
            
            if token in self.htrue:
                hash_info['true'] += 1
                true_words.add(token)
            elif token in self.hfalse:
                hash_info['false'] += 1
                false_words.add(token)
            elif token in self.hconflict:
                hash_info['conflict'] += 1
                conflict_words.add(token)
                
        return dict(hash_info), true_words, false_words, conflict_words


class NGWordProcessor:
    """NGワード処理クラス"""
    
    def __init__(self, debug=False):
        self.debug = debug
        self.ng = {}
        self.ng_pattern = {}
        
    def get_nglist(self, file_nglist: str):
        """
        NGワードリストを読み込む
        
        Args:
            file_nglist (str): NGワードファイルのパス
        """
        cnt = 0
        try:
            with open(file_nglist, 'r', encoding='utf-8') as fp:
                for line in fp:
                    word = line.strip()
                    
                    if '?' in word:
                        try:
                            compiled_regex = re.compile(word)
                            self.ng_pattern[word] = {'compiled': compiled_regex}
                        except re.error:
                            pass
                    
                    word_len = len(word)
                    first_letter = word[0] if word else ''
                    
                    if word_len not in self.ng:
                        self.ng[word_len] = {}
                    if first_letter not in self.ng[word_len]:
                        self.ng[word_len][first_letter] = {}
                    
                    self.ng[word_len][first_letter][word] = 1
                    cnt += 1
                    
            testline = ','.join(map(str, sorted(self.ng.keys())))
            print(f"#ng_words:{cnt}; {testline}", file=sys.stderr)
            
        except Exception as e:
            print(f"Error reading NG word file: {e}", file=sys.stderr)
            
    def remove_ng_word_regex(self, title: str) -> str:
        """
        正規表現ベースのNG表現削除
        
        Args:
            title (str): 処理対象のタイトル
            
        Returns:
            str: 処理後のタイトル
        """
        # 日付・時刻関連
        title = re.sub(r'-\d+迄', '', title)
        title = re.sub(r'-\d+(は|まで)', '', title)
        title = re.sub(r'\d+(迄|まで|代)', '', title)
        title = re.sub(r'(20|19)\d+年', '', title)
        title = re.sub(r'\d+月\d+日', '', title)
        title = re.sub(r'\d+月', '', title)
        title = re.sub(r'\d+日間', '', title)
        title = re.sub(r'\d+日', '', title)
        
        # 価格・割引関連
        title = re.sub(r'\d+円引(き|)', '', title)
        title = re.sub(r'全\d+色', '', title)
        title = re.sub(r'増量\d+倍', '', title)
        title = re.sub(r'いずれか\d+点', '', title)
        title = re.sub(r'ポイント\d+倍', '', title)
        title = re.sub(r'\d+月(上旬|中旬|下旬)', '', title)
        title = re.sub(r'(先着|抽選)\d+(人|名)(様|)', '', title, flags=re.IGNORECASE)
        title = re.sub(r'(最大|)\d+円off', '', title, flags=re.IGNORECASE)
        title = re.sub(r'(最大|)p\d+倍', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\d+円off', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\d+円', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\d+%off', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\d+/\d+\((月|火|水|木|金|土|日)\)', '', title)
        title = re.sub(r'\d+/\d+ \d+:\d+-\d+:\d+', '', title)
        title = re.sub(r'\d+%ポイントバック', '', title)
        title = re.sub(r'スーパーsale', '', title, flags=re.IGNORECASE)
        title = re.sub(r'(協賛|)ポイント(最大|)([1-9]\d*|0)(\.[0-9]+)?倍(!|)', '', title)
        title = re.sub(r'\d+/\d+-\d+/\d+', '', title)
        title = re.sub(r'\d+/\d+-\d+:\d+', '', title)
        title = re.sub(r'\d+/\d+ \d+:\d+-', '', title)
        title = re.sub(r'\d+/\d+ \d+:\d+', '', title)
        title = re.sub(r'\d+:\d+(am|pm)', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\d+:\d+', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\((日|月|火|水|木|金|土)\)\d+時\d+分までエントリー', '', title)
        title = re.sub(r'(1|2|3|4|5|6|7|8|9|10|11|12)/\d+', '', title)
        
        # 記号・数字のみの削除
        title = re.sub(r'^[0-9!@#$%^&*_+\-=]+\s', '', title)
        title = re.sub(r'\s[0-9!@#$%^&*_+\-=]+\s', ' ', title)
        title = re.sub(r'\s[0-9!@#$%^&*_+\-=]+$', '', title)
        
        # 単位付き数値
        title = re.sub(r'^([0-9,]+)?(個|本|枚|回|袋|ml|g|kg|l)(入り|入|セット|)\s', '', title)
        title = re.sub(r'\s([0-9,]+)?(個|本|枚|回|袋|ml|g|kg|l)(入り|入|セット|)\s', ' ', title)
        title = re.sub(r'\s([0-9,]+)?(個|本|枚|回|袋|ml|g|kg|l)(入り|入|セット|)$', '', title)
        
        # 空白の正規化
        title = re.sub(r'\s+', ' ', title)
        title = title.strip()
        
        return title
        
    def remove_ng_words(self, title: str) -> str:
        """
        NGワードを削除（正規表現＋単語ベース）
        
        Args:
            title (str): 処理対象のタイトル
            
        Returns:
            str: 処理後のタイトル
        """
        title = self.remove_ng_word_regex(title)
        
        mytitle_len = len(title)
        
        for i in range(len(title)):
            for word_len in sorted(self.ng.keys(), reverse=True):
                if word_len + i > mytitle_len:
                    continue
                    
                target = title[i:i+word_len]
                
                if not target:
                    continue
                    
                first_char = target[0]
                
                if (word_len in self.ng and 
                    first_char in self.ng[word_len] and 
                    target in self.ng[word_len][first_char]):
                    
                    title = title.replace(target, '')
                    return self.remove_ng_words(title)
                    
        return title


class DataProcessor:
    """データ処理メインクラス"""
    
    def __init__(self, args):
        self.args = args
        self.debug = args.debug
        
    def get_info_from_example(self, flag: str, example: str) -> Tuple:
        """
        事例から情報を抽出
        
        Args:
            flag (str): 処理フラグ（"NO_PREDICTION" or "PREDICTION"）
            example (str): 入力行
            
        Returns:
            Tuple: (prediction, index, ptitle, ititle, g1_name)
        """
        parts = example.split('\t')
        
        if flag == "NO_PREDICTION":
            if len(parts) < 11:
                return None, None, None, None, None
            index, gtruth, rancode, ptitle, ititle = parts[0], parts[1], parts[2], parts[3], parts[4]
            g1_name = parts[8] if len(parts) > 8 else ''
            return gtruth.upper(), index, ptitle, ititle, g1_name
            
        elif flag == "PREDICTION":
            if len(parts) < 12:
                return None, None, None, None, None
            prediction, index, gtruth, rancode, ptitle, ititle = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
            g1_name = parts[9] if len(parts) > 9 else ''
            return prediction, index, ptitle, ititle, g1_name
            
        else:
            print("ERROR! in get_info_from_example(): wrong flag", file=sys.stderr)
            return None, None, None, None, None
            
    def filter_data(self):
        """フィルタリング処理"""
        token_proc = TokenProcessor(self.debug)
        token_proc.read_tokens(self.args.f)
        
        # 追加トークンの読み込み
        if self.args.add:
            try:
                with open(self.args.add, 'r', encoding='utf-8') as fa:
                    for line in fa:
                        line = line.strip()
                        parts = line.split('\t')
                        
                        if len(parts) < 4:
                            continue
                            
                        flag, true_num, false_num, token = parts[0], parts[1], parts[2], parts[3]
                        
                        if flag in ["対象", "TRUE"]:
                            token_proc.htrue[token] = int(true_num)
                            if token in token_proc.hconflict:
                                del token_proc.hconflict[token]
                        elif flag in ["対象外", "非対象", "FALSE"]:
                            token_proc.hfalse[token] = int(false_num)
                            if token in token_proc.hconflict:
                                del token_proc.hconflict[token]
                                
                if self.debug:
                    print(f"File:{self.args.add}\t#tokens_in_True:{len(token_proc.htrue)}\t"
                          f"#tokens_in_False:{len(token_proc.hfalse)}\t"
                          f"#tokens_in_Conflict:{len(token_proc.hconflict)}",
                          file=sys.stderr)
            except Exception as e:
                print(f"Error reading add file: {e}", file=sys.stderr)
        
        # 標準入力からデータを処理
        for line in sys.stdin:
            line = line.strip()
            parts = line.split('\t')
            
            if len(parts) < 11:
                continue
                
            index, gtruth, rancode, ptitle, ititle = parts[0], parts[1], parts[2], parts[3], parts[4]
            
            # タイトルの前処理
            new_ititle = re.sub(r'[\[\]\|]', ' ', ititle)
            new_ititle = re.sub(r'\s+', ' ', new_ititle)
            
            hash_info = defaultdict(int)
            true_words = set()
            false_words = set()
            conflict_words = set()
            
            # ititleからトークン抽出
            if new_ititle:
                info, tw, fw, cw = token_proc.get_tokens_from_title(new_ititle)
                for key, val in info.items():
                    hash_info[key] += val
                true_words.update(tw)
                false_words.update(fw)
                conflict_words.update(cw)
            
            # ptitleからトークン抽出
            if ptitle:
                info, tw, fw, cw = token_proc.get_tokens_from_title(ptitle)
                for key, val in info.items():
                    hash_info[key] += val
                true_words.update(tw)
                false_words.update(fw)
                conflict_words.update(cw)
            
            # 統計情報の計算
            num_tokens = hash_info.get('length', 0)
            num_true = hash_info.get('true', 0)
            num_false = hash_info.get('false', 0)
            num_conflict = hash_info.get('conflict', 0)
            
            ratio_true = num_true / num_tokens if num_tokens > 0 else 0
            ratio_false = num_false / num_tokens if num_tokens > 0 else 0
            ratio_conflict = num_conflict / num_tokens if num_tokens > 0 else 0
            
            wlist_true = ';'.join(true_words)
            wlist_false = ';'.join(false_words)
            wlist_conflict = ';'.join(conflict_words)
            
            # 判定
            if num_true == 0 and num_false == 0:
                answer = "UNKNOWN"
            elif num_true >= num_false:
                answer = "TRUE"
            else:
                answer = "FALSE"
            
            print(f"{answer}\t{line}\t{ratio_true}({num_true})/{ratio_false}({num_false})/"
                  f"{ratio_conflict}({num_conflict})#{num_tokens}\t{wlist_true};;;{wlist_false}")
                  
    def main_processing(self, flag: str):
        """メイン処理"""
        print(f"main(), flag:{flag}", file=sys.stderr)
        
        prod = defaultdict(int)
        item = defaultdict(int)
        hash_tokens = defaultdict(int)
        comp = defaultdict(lambda: defaultdict(lambda: {
            'freq': 0,
            'idx': defaultdict(int),
            'g1name': defaultdict(int)
        }))
        
        for line in sys.stdin:
            line = line.strip()
            prediction, index, ptitle, ititle, g1_name = self.get_info_from_example(flag, line)
            
            if not prediction:
                continue
            
            # タイトルの前処理
            new_ititle = re.sub(r'[\[\]\|]', ' ', ititle) if ititle else ''
            new_ititle = re.sub(r'\s+', ' ', new_ititle)
            
            if not ptitle:
                ptitle = new_ititle
            
            # トークン処理
            for token in ptitle.split():
                hash_tokens[token] += 1
                comp[token][prediction]['freq'] += 1
                comp[token][prediction]['idx'][index] += 1
                comp[token][prediction]['g1name'][g1_name] += 1
                prod[token] += 1
        
        self.put_token_list(hash_tokens, comp, item, prod)
        
    def put_token_list(self, hash_tokens: Dict, comp: Dict, item: Dict, prod: Dict):
        """トークンリストの出力"""
        for token in sorted(hash_tokens.keys()):
            # フィルタリング
            if len(token) < 2:
                continue
            if not re.search(r'\w', token):
                continue
            if re.match(r'^\d+$', token):
                continue
            if re.match(r'^[0-9,]+(kg|g|ml|l)$', token):
                continue
            
            # フラグの設定
            flags = []
            if token in item:
                flags.append("Item")
            if token in prod:
                flags.append("Prod")
            flag = "/".join(flags) if flags else "NONE"
            
            # TRUE/FALSE頻度
            true_num = comp[token]["TRUE"]['freq'] if "TRUE" in comp[token] else 0
            false_num = comp[token]["FALSE"]['freq'] if "FALSE" in comp[token] else 0
            
            # インデックスリスト
            true_idxlist = ','.join(map(str, sorted(comp[token]["TRUE"]['idx'].keys(),key=int))) if "TRUE" in comp[token] else "NO_TRUE_LIST"
            false_idxlist = ','.join(map(str, sorted(comp[token]["FALSE"]['idx'].keys(),key=int))) if "FALSE" in comp[token] else "NO_FALSE_LIST"
            
            # G1名リスト
            true_g1name_list = self.get_g1name_list(comp, token, "TRUE")
            false_g1name_list = self.get_g1name_list(comp, token, "FALSE")
            
            if self.args.idx:
                print(f"{true_num}\t{false_num}\t{token}\t{flag}\t{true_idxlist}\t{false_idxlist}")
            else:
                print(f"{true_num}\t{false_num}\t{token}\t{flag}")
                
    def get_g1name_list(self, comp: Dict, token: str, flag: str) -> str:
        """L1ジャンル名とその頻度の取得"""
        if flag not in comp[token]:
            return ""
            
        tmp = []
        for g1name, freq in comp[token][flag]['g1name'].items():
            tmp.append(f"{g1name}:{freq}")
        
        return ','.join(tmp)
        
    def main_ng_word(self, flag: str):
        """NGワードを使用したメイン処理"""
        print("main_ng_words()", file=sys.stderr)
        
        # NGワードリストの読み込み
        ng_proc = NGWordProcessor(self.debug)
        ng_proc.get_nglist(self.args.f)
        
        prod = defaultdict(int)
        item = defaultdict(int)
        hash_tokens = defaultdict(int)
        comp = defaultdict(lambda: defaultdict(lambda: {
            'freq': 0,
            'idx': defaultdict(int),
            'g1name': defaultdict(int)
        }))
        
        for line in sys.stdin:
            line = line.strip()
            prediction, index, ptitle, ititle, g1_name = self.get_info_from_example(flag, line)
            
            if not prediction:
                continue
            
            # タイトルの前処理
            new_ititle = re.sub(r'[\[\]\|]', ' ', ititle) if ititle else ''
            new_ititle = re.sub(r'\s+', ' ', new_ititle)
            
            if not ptitle:
                ptitle = new_ititle
            
            # NGワード削除
            ptitle = re.sub(r'[\[\]\|]', ' ', ptitle)
            ptitle = re.sub(r'\s+', ' ', ptitle)
            ptitle = ng_proc.remove_ng_words(ptitle)
            
            # トークン処理
            for token in ptitle.split():
                hash_tokens[token] += 1
                comp[token][prediction]['freq'] += 1
                comp[token][prediction]['idx'][index] += 1
                comp[token][prediction]['g1name'][g1_name] += 1
                prod[token] += 1
        
        self.put_token_list(hash_tokens, comp, item, prod)


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='JANコード処理スクリプト')
    parser.add_argument('--debug', action='store_true', help='デバッグモード')
    parser.add_argument('-filter', '--filter', action='store_true', help='フィルタリング処理')
    parser.add_argument('-checkwords', '--checkwords', action='store_true', help='ワードチェック')
    parser.add_argument('--add', type=str, help='追加ファイル')
    parser.add_argument('--pick', action='store_true', help='未知の例を抽出')
    parser.add_argument('-f', type=str, help='入力ファイル1')
    parser.add_argument('--f2', type=str, help='入力ファイル2')
    parser.add_argument('-ng', '--ng', action='store_true', help='NGワード処理')
    parser.add_argument('-orig', '--orig', action='store_true', help='オリジナル処理')
    parser.add_argument('-idx', '--idx', action='store_true', help='インデックス出力')
    parser.add_argument('--update', action='store_true', help='LLMアノテーション更新')
    parser.add_argument('-refine', '--refine', action='store_true', help='ラベル精緻化')
    parser.add_argument('-pm', '--pm', type=str, help='製品マスターファイル')
    parser.add_argument('-pbrand', '--pbrand', type=str, help='製品ブランド')
    parser.add_argument('-cbrand', '--cbrand', type=str, help='会社ブランド')
    
    args = parser.parse_args()
    
    processor = DataProcessor(args)
    
    if args.filter:
        processor.filter_data()
    elif args.checkwords:
        check_words()
    elif args.update:
        update_llm_annotation(args)
    elif args.pick:
        pick_unknown_examples(args)
    elif args.refine:
        refine_label_rancode(args)
    elif args.ng:
        processor.main_ng_word("PREDICTION")
    else:
        if args.orig:
            processor.main_processing("NO_PREDICTION")
        else:
            processor.main_processing("PREDICTION")


def check_words():
    """トークンの数の数え上げ"""
    hash_count = defaultdict(int)
    cnt = 0
    
    for line in sys.stdin:
        line = line.strip()
        parts = line.split('\t')
        
        if len(parts) < 3:
            continue
            
        t, f, token = int(parts[0]), int(parts[1]), parts[2]
        
        if t == 0:
            hash_count['false'] += 1
        elif f == 0:
            hash_count['true'] += 1
        else:
            hash_count['conflict'] += 1
        cnt += 1
    
    tmp = [f"{flag}:{hash_count[flag]}" for flag in ['true', 'false', 'conflict']]
    line = ','.join(tmp)
    print(f"{line} (total {cnt})")


def update_llm_annotation(args):
    """LLMアノテーションの更新"""
    hash_updates = {}
    
    try:
        with open(args.f, 'r', encoding='utf-8') as fp:
            for line in fp:
                line = line.strip()
                parts = line.split('\t')
                
                if len(parts) < 6:
                    continue
                    
                tag, freq_true, freq_false, token, list_true, list_false = parts[:6]
                tag = tag.lower()
                
                if tag not in ["true", "false"]:
                    continue
                
                if tag == "true":
                    for idx in list_false.split(','):
                        hash_updates[idx] = "TRUE"
                elif tag == "false":
                    for idx in list_true.split(','):
                        hash_updates[idx] = "FALSE"
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
    
    for line in sys.stdin:
        line = line.strip()
        parts = line.split('\t', 1)
        
        if len(parts) < 2:
            print(line)
            continue
            
        ann, info = parts[0], parts[1]
        idx = info.split(',')[0]
        
        if idx not in hash_updates:
            print(line)
        else:
            print(f"{hash_updates[idx]}\t{info}")


def pick_unknown_examples(args):
    """未知の例を抽出"""
    hash_pred = {}
    
    try:
        with open(args.f, 'r', encoding='utf-8') as fp:
            for line in fp:
                parts = line.strip().split('\t')
                if len(parts) >= 2:
                    pred, idx = parts[0], parts[1]
                    hash_pred[idx] = pred
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
    
    for line in sys.stdin:
        line = line.strip()
        parts = line.split('\t')
        
        if len(parts) < 2:
            continue
            
        pred, idx = parts[0], parts[1]
        
        if pred != "UNKNOWN":
            print(line)
            continue
        
        idx = idx.strip()
        
        if idx in hash_pred:
            others = '\t'.join(parts[2:])
            print(f"{hash_pred[idx]}\t{idx}\t{others}")


def refine_label_rancode(args):
    """ラベルの精緻化処理"""
    # 製品マスター情報の読み込み
    pm_proc = ProductMasterProcessor()
    pm_proc.get_pm_info(args.pm)
    
    p_brand = args.pbrand.lower() if args.pbrand else ''
    c_brand = args.cbrand.lower() if args.cbrand else ''
    
    print(f"C_brand: {c_brand} / P_brand: {p_brand}", file=sys.stderr)
    
    hash_rancode = {}
    lines = []
    
    # rancode毎の統計情報収集
    for line in sys.stdin:
        line = line.strip()
        lines.append(line)
        parts = line.split('\t')
        
        if len(parts) < 4:
            continue
            
        prediction, index, gtruth, rancode = parts[0], parts[1], parts[2], parts[3]
        
        if rancode == "0":
            continue
        
        if rancode not in hash_rancode:
            hash_rancode[rancode] = {'pred': defaultdict(int)}
        
        hash_rancode[rancode]['pred'][prediction] += 1
    
    print(f"rancode size:{len(hash_rancode)}", file=sys.stderr)
    
    # rancode毎の判定
    for rancode in hash_rancode:
        total = sum(hash_rancode[rancode]['pred'].values())
        num_true = hash_rancode[rancode]['pred'].get('TRUE', 0)
        
        hash_rancode[rancode]['ratio'] = num_true / total if total > 0 else 0
        hash_rancode[rancode]['total'] = total
        
        if (num_true / total) > 0.5:
            hash_rancode[rancode]['ans'] = "TRUE"
        else:
            hash_rancode[rancode]['ans'] = "NONE"
    
    print(f"size_line: {len(lines)}", file=sys.stderr)
    
    # 各行の処理
    jan_processor = JanCodeProcessor()
    
    for line in lines:
        parts = line.split('\t')
        
        if len(parts) < 12:
            print(line)
            continue
        
        prediction, index, gtruth, rancode = parts[0], parts[1], parts[2], parts[3]
        
        if rancode == "0":
            print(line)
            continue
        
        jancode = rancode.replace('1001000', '')
        company_code = jan_processor.get_companycode_from_jancode(jancode)
        company_code = "10" + company_code
        
        # 過半数がTRUEの場合
        ratio_true = hash_rancode[rancode].get('ratio', 0)
        
        if ratio_true > 0.5:
            parts[0] = "TRUE"
            print('\t'.join(parts))
            continue
        
        # PMチェック
        if company_code not in pm_proc.pm_code:
            print(line)
            continue
        
        if company_code not in pm_proc.pm or jancode not in pm_proc.pm[company_code]:
            print(line)
            continue
        
        # ブランドチェック
        c_flag = False
        p_flag = False
        
        pm_entry = pm_proc.pm[company_code][jancode]
        
        # 会社名チェック
        if pm_entry.get('name') and c_brand in pm_entry['name'].lower():
            c_flag = True
        if pm_entry.get('mname') and c_brand in pm_entry['mname'].lower():
            c_flag = True
        
        # ブランドチェック
        if pm_entry.get('b') and (p_brand in pm_entry['b'].lower() or pm_entry['b'].lower() in p_brand):
            p_flag = True
        
        for pm_brand in pm_entry.get('mb', {}).keys():
            if p_brand in pm_brand.lower() or pm_brand.lower() in p_brand:
                p_flag = True
                break
        
        # 両方マッチする場合はTRUEに変更
        if p_flag and c_flag:
            parts[0] = "TRUE"
        
        print('\t'.join(parts))


if __name__ == "__main__":
    main()

