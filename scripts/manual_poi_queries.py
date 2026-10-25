"""补充难搜景点的精准英文检索词（覆盖手工修正 + 二次检索）。"""
from __future__ import annotations

import io
import json
import sys

sys.path.insert(0, r"D:\文旅助手")

from app.services import poi as poi_svc  # noqa: E402

OUT = io.open("D:/shot_tmp/poi_q_manual.txt", "w", encoding="utf-8")
TARGET = r"D:\文旅助手\app\data\poi_queries.json"

# city_id -> {景点名: [更准的检索词]}
MANUAL = {
    "chongqing": {
        "长江索道": ["chongqing yangtze river cableway", "chongqing cable car", "chongqing"],
        "洪崖洞": ["hongyadong chongqing", "chongqing night", "hongya cave"],
        "解放碑": ["jiefangbei chongqing", "chongqing city center", "chongqing"],
        "李子坝轻轨穿楼": ["liziba station chongqing", "train through building chongqing", "chongqing metro"],
        "磁器口古镇": ["ciqikou ancient town", "chongqing old town", "ancient street china"],
        "武隆天生三桥": ["wulong tiankeng three bridges", "wulong karst", "wulong"],
        "南山一棵树观景台": ["nanshan tree chongqing", "chongqing night view", "chongqing skyline"],
        "鹅岭二厂": ["eling park chongqing", "chongqing vintage factory", "chongqing park"],
    },
    "guiyang": {
        "甲秀楼": ["jiaxiu pavilion guiyang", "guiyang old town", "guizhou pavilion"],
        "黔灵山公园": ["qianling mountain park guiyang", "guizhou mountain park", "guiyang park"],
        "天河潭": ["tianhe tan waterfall guiyang", "guizhou waterfall", "guizhou nature"],
        "贵州省博物馆": ["guizhou provincial museum", "guizhou museum", "museum china"],
        "青云市集": ["qingyun market guiyang", "guizhou night market", "chinese night market"],
        "青岩古镇": ["qingyan ancient town guizhou", "guizhou old town", "guizhou village"],
        "花溪公园": ["huaxi park guiyang", "guizhou park", "china city park"],
        "高坡云顶草原": ["guizhou grassland", "yunfeng plateau", "china grassland"],
    },
    "qiandongnan": {
        "西江千户苗寨": ["xijiang miao village", "miao ethnic village", "guizhou village"],
        "肇兴侗寨": ["zhaoxing dong village", "dong ethnic village", "guizhou village"],
        "镇远古镇": ["zhenyuan ancient town", "guizhou old town river", "ancient town china"],
        "朗德上寨": ["langde miao village", "miao village", "ethnic village china"],
    },
    "anshun": {
        "黄果树瀑布": ["huangguoshu waterfall", "guizhou waterfall", "china waterfall"],
        "龙宫": ["longgong cave guizhou", "guizhou cave", "karst cave china"],
        "天龙屯堡": ["tianlong tunpu fortress", "guizhou fortress village", "china fortress village"],
        "旧州古镇": ["jiuzhou ancient town guizhou", "guizhou old town", "china ancient town"],
        "虹山湖公园": ["hongshan lake guizhou", "guizhou lake park", "china lake park"],
    },
    "zunyi": {
        "遵义会议会址": ["zunyi conference site", "zunyi museum", "china revolution museum"],
        "赤水丹霞·佛光岩": ["chishui danxia", "guizhou red rock mountain", "danxia landform"],
        "茅台镇": ["maotai town", "maotai distillery", "guizhou liquor town"],
        "娄山关": ["loushan pass", "zunyi mountain pass", "guizhou mountain pass"],
        "四洞沟": ["sidonggou waterfall", "guizhou canyon waterfall", "china waterfall valley"],
        "海龙屯": ["hailongtun fortress", "guizhou ancient fortress", "china hilltop fortress"],
    },
    "xian": {
        "秦始皇兵马俑": ["terracotta army xian", "terracotta warriors", "china statue army"],
        "大唐不夜城": ["datang ever bright city", "xian night", "xian tang dynasty"],
        "西安城墙": ["xian city wall", "xian ancient wall", "china city wall"],
        "陕西历史博物馆": ["shaanxi history museum xian", "xian museum", "china history museum"],
        "回民街": ["huimin street xian", "xian food street", "chinese food street night"],
        "大雁塔": ["giant wild goose pagoda xian", "xian pagoda", "china pagoda"],
        "钟鼓楼广场": ["xian bell tower", "xian drum tower", "china bell tower"],
        "华清宫": ["huaqing palace xian", "terracotta army museum", "china palace"],
    },
    "chengdu": {
        "大熊猫繁育研究基地": ["giant panda breeding base chengdu", "panda base", "giant panda"],
        "宽窄巷子": ["kuanzhai alley chengdu", "chengdu old street", "china alley"],
        "都江堰": ["dujiangyan irrigation", "dujiangyan dam", "china ancient dam"],
        "锦里古街": ["jinli street chengdu", "chengdu ancient street", "china lantern street"],
        "宽窄巷子·井巷子": ["chengdu alley", "sichuan old street", "china narrow alley"],
        "青羊宫": ["qingyang palace chengdu", "taoist temple sichuan", "china taoist temple"],
        "武侯祠": ["wuhou shrine chengdu", "three kingdoms shrine", "china temple garden"],
        "人民公园鹤鸣茶社": ["heming teahouse chengdu", "sichuan tea house", "chinese teahouse"],
    },
    "xiamen": {
        "鼓浪屿": ["gulangyu island xiamen", "xiamen island", "china island street"],
        "曾厝垵": ["zengcuoan village", "xiamen village", "china village street"],
        "南普陀寺": ["nanputuo temple xiamen", "xiamen temple", "china temple"],
        "环岛路": ["xiamen huandao road", "xiamen coast", "china seaside road"],
        "沙坡尾": ["shapowei xiamen", "xiamen harbor", "china harbor"],
        "胡里山炮台": ["huli shan fort xiamen", "xiamen fort", "china coastal fort"],
        "厦门大学": ["xiamen university", "xiamen campus", "china university campus"],
        "厦门海鲜大排档": ["xiamen seafood", "chinese seafood stall", "seafood market china"],
    },
    "guilin": {
        "漓江竹筏·兴坪": ["li river guilin bamboo raft", "guilin karst river", "li river"],
        "阳朔西街": ["yangshuo west street", "guilin yangshuo town", "china town street night"],
        "龙脊梯田": ["longji rice terraces", "guilin terraces", "china rice terrace"],
        "十里画廊": ["shili gallery guilin", "guilin karst mountain road", "guilin scenery"],
        "两江四湖": ["liangjiang four lakes guilin", "guilin night lake", "guilin night view"],
        "银子岩": ["yinzi cave guilin", "guilin cave", "guilin karst cave"],
        "遇龙河": ["yulong river guilin", "guilin river bamboo", "karst river china"],
        "印象刘三姐": ["impression liu san jie", "guilin li river performance", "river performance china"],
    },
    "shanghai": {
        "外滩": ["the bund shanghai", "shanghai skyline", "shanghai pudong night"],
        "东方明珠": ["oriental pearl tower", "shanghai tv tower", "shanghai landmark"],
        "豫园": ["yuyuan garden shanghai", "shanghai old city", "china garden"],
        "南京东路": ["nanjing road shanghai", "shanghai shopping street", "china shopping street"],
        "田子坊": ["tianzifang shanghai", "shanghai art lane", "china miao kiln street"],
        "武康路": ["wukang road shanghai", "shanghai street trees", "shanghai french concession"],
        "上海迪士尼乐园": ["shanghai disneyland", "disney castle", "theme park china"],
        "上海博物馆": ["shanghai museum", "china bronze museum", "china history museum"],
    },
    "beijing": {
        "故宫": ["forbidden city beijing", "palace museum beijing", "china imperial palace"],
        "天安门广场": ["tiananmen square", "beijing square", "china landmark square"],
        "颐和园": ["summer palace beijing", "beijing lake garden", "china imperial garden"],
        "八达岭长城": ["badaling great wall", "great wall of china", "mutianyu great wall"],
        "天坛公园": ["temple of heaven beijing", "beijing temple", "china round temple"],
        "圆明园": ["yuanmingyu ruins", "old summer palace beijing", "china ruins garden"],
        "北京环球影城": ["universal beijing resort", "beijing theme park", "theme park castle"],
        "北海公园": ["beihai park beijing", "beijing lake park", "china imperial lake"],
    },
    "hangzhou": {
        "西湖": ["west lake hangzhou", "hangzhou lake", "china lake pagoda"],
        "灵隐寺": ["lingyin temple hangzhou", "hangzhou buddhist temple", "china temple forest"],
        "西溪湿地": ["xixi wetland hangzhou", "hangzhou wetland", "china marsh"],
        "雷峰塔": ["leifeng pagoda hangzhou", "hangzhou pagoda", "china pagoda sunset"],
        "河坊街": ["hefang street hangzhou", "hangzhou old street", "china old street"],
        "京杭大运河杭州段": ["grand canal hangzhou", "hangzhou canal", "china canal boats"],
        "六和塔": ["liuhe pagoda hangzhou", "hangzhou pagoda river", "china pagoda"],
        "良渚文化遗址": ["liangzhu ruins", "hangzhou archaeological site", "china ancient ruins"],
    },
    "kunming": {
        "斗南花市": ["dounan flower market", "kunming flower market", "china flower market"],
        "滇池": ["dianchi lake kunming", "kunming lake", "china lake gulls"],
        "翠湖公园": ["cuihu park kunming", "kunming park", "china city park lake"],
        "石林": ["stone forest kunming", "yunnan karst stone forest", "china karst"],
        "东川红土地": ["dongchuan red land", "yunnan red soil", "red earth landscape china"],
        "昙华寺": ["tanhua temple kunming", "kunming temple", "china temple garden"],
        "官渡古镇": ["guandu ancient town", "yunnan old town", "china ancient town"],
        "云南民族村": ["yunnan nationalities village", "china ethnic village", "china minority village"],
    },
    "dali": {
        "大理古城": ["dali ancient town", "yunnan old town", "china ancient town"],
        "洱海": ["erhai lake dali", "dali lake", "china lake mountains"],
        "崇圣寺三塔": ["three pagodas dali", "dali pagoda", "china three pagodas"],
        "喜洲古镇": ["xizhou town dali", "bai village dali", "yunnan village"],
        "双廊": ["shuanglang dali", "erhai lakeside village", "china lakeside village"],
        "苍山": ["cangshan mountain dali", "yunnan mountain snow", "china mountain"],
        "南诏风情岛": ["nanzhao island dali", "erhai island", "china lake island"],
        "才村码头": ["caicun pier dali", "erhai pier", "china lake pier"],
    },
    "lijiang": {
        "丽江古城": ["lijiang old town", "yunnan ancient town", "china old town night"],
        "束河古镇": ["shuhe old town lijiang", "lijiang village", "china ancient village"],
        "玉龙雪山": ["jade dragon snow mountain", "yunnan snow mountain", "china snow peak"],
        "拉市海": ["lashi lake lijiang", "yunnan wetland lake", "china wetland birds"],
        "虎跳峡": ["tiger leaping gorge", "yunnan canyon river", "china gorge"],
        "蓝月谷": ["blue moon valley lijiang", "yunnan valley lake", "china blue lake"],
        "白沙古镇": ["baisha village lijiang", "naxi village", "china village naxi"],
        "黑龙潭公园": ["black dragon pool lijiang", "yunnan temple pool", "china temple lake"],
    },
    "nanjing": {
        "中山陵": ["sun yat-sen mausoleum nanjing", "nanjing mausoleum", "china memorial hall"],
        "夫子庙·秦淮河": ["fuzimiao nanjing", "nanjing confucius temple", "china night canal"],
        "老门东": ["laomendong nanjing", "nanjing old street", "china old district"],
        "南京博物院": ["nanjing museum", "china history museum", "china museum building"],
        "明孝陵": ["ming tombs nanjing", "nanjing imperial tomb", "china tree tomb"],
        "总统府": ["nanjing presidential palace", "china republican palace", "china historic house"],
        "玄武湖": ["xuanwu lake nanjing", "nanjing lake", "china city lake"],
        "先锋书店": ["pioneer bookshop nanjing", "china bookstore", "china bookshop interior"],
    },
    "suzhou": {
        "拙政园": ["humble administrator garden suzhou", "suzhou garden", "china classical garden"],
        "留园": ["lingering garden suzhou", "suzhou classical garden", "china rockery garden"],
        "平江路": ["pingjiang road suzhou", "suzhou canal street", "china canal town"],
        "虎丘": ["huqiu suzhou", "suzhou hill pagoda", "china pagoda hill"],
        "寒山寺": ["hanshan temple suzhou", "suzhou temple bell", "china buddhist temple"],
        "同里古镇": ["tongli ancient town", "jiangnan water town", "china canal town"],
        "耦园": ["ouyuan garden suzhou", "suzhou couple garden", "china garden corridor"],
        "金鸡湖": ["jinji lake suzhou", "suzhou modern skyline", "china lake city night"],
    },
    "changsha": {
        "太平老街": ["taiping street changsha", "changsha old street", "china old street night"],
        "文和友老长沙": ["wenheyou changsha", "changsha food street", "china retro food street"],
        "橘子洲头": ["orange isle changsha", "changsha river island", "china river island monument"],
        "岳麓山": ["yuelu mountain changsha", "changsha mountain", "china mountain academy"],
        "湖南省博物馆": ["hunan museum changsha", "china museum", "china bronze museum"],
        "岳麓书院": ["yuelu academy changsha", "china ancient academy", "china garden school"],
        "长沙世界之窗": ["changsha window of world", "china amusement park", "theme park china"],
        "谢子龙影像艺术馆": ["changsha art museum", "china art museum", "modern museum china"],
    },
    "harbin": {
        "冰雪大世界": ["harbin ice snow festival", "china ice sculpture festival", "ice sculpture night"],
        "中央大街": ["central street harbin", "harbin old street", "china baroque street"],
        "圣索菲亚教堂": ["sofia cathedral harbin", "harbin church", "china orthodox church"],
        "太阳岛公园": ["sun island park harbin", "harbin park winter", "china snow park"],
        "东北虎林园": ["harbin tiger park", "siberian tiger park", "china tiger park"],
        "亚布力滑雪": ["yabuli ski resort", "china ski resort", "ski slope china"],
        "松花江": ["songhua river harbin", "harbin frozen river", "china frozen river"],
        "老道外中华巴洛克": ["harbin baroque district", "china baroque architecture", "old district china"],
    },
    "qingdao": {
        "栈桥": ["zhanqiao pier qingdao", "qingdao pier", "china pier lighthouse"],
        "劈柴院": ["pichaiyuan qingdao", "qingdao old food street", "china food alley"],
        "八大关": ["badaguan qingdao", "qingdao villa district", "china tree street villas"],
        "崂山": ["laoshan qingdao", "qingdao mountain sea", "china coastal mountain"],
        "金沙滩": ["golden beach qingdao", "qingdao beach", "china sand beach"],
        "小麦岛": ["xiaomai island qingdao", "qingdao island park", "china sea island"],
        "青岛啤酒博物馆": ["tsingtao beer museum", "qingdao beer", "china brewery"],
        "信号山公园": ["signal hill qingdao", "qingdao hill view", "china hill park"],
    },
    "wuhan": {
        "黄鹤楼": ["yellow crane tower wuhan", "wuhan tower", "china pagoda river"],
        "东湖": ["east lake wuhan", "wuhan lake", "china lake cherry"],
        "户部巷": ["hubu lane wuhan", "wuhan food street", "china snack street"],
        "武汉大学": ["wuhan university", "china university cherry blossom", "china campus cherry"],
        "湖北省博物馆": ["hubei provincial museum", "china museum", "china museum bronze"],
        "江汉路步行街": ["jianghan road wuhan", "wuhan shopping street", "china pedestrian street"],
        "知音号": ["zhiyin ship wuhan", "wuhan cruise ship", "china river cruise"],
        "长江大桥": ["wuhan yangtze bridge", "china river bridge", "wuhan bridge night"],
    },
    "guangzhou": {
        "广州塔": ["canton tower guangzhou", "guangzhou tower", "china tower night"],
        "陈家祠": ["chenci temple guangzhou", "guangzhou ancestral hall", "china folk art museum"],
        "沙面岛": ["shamian island guangzhou", "guangzhou colonial island", "china island trees"],
        "永庆坊": ["yongqingfang guangzhou", "guangzhou old neighborhood", "china xiguan house"],
        "白云山": ["baiyun mountain guangzhou", "guangzhou mountain", "china mountain park"],
        "广东省博物馆": ["guangdong museum guangzhou", "china museum", "china art museum"],
        "珠江夜游": ["pearl river night cruise guangzhou", "guangzhou night cruise", "china river night cruise"],
        "长隆野生动物世界": ["chimelong safari guangzhou", "china safari park", "china wildlife park"],
    },
    "shenzhen": {
        "深圳湾公园": ["shenzhen bay park", "shenzhen bay", "china bay park"],
        "世界之窗": ["window of the world shenzhen", "china theme park", "china miniature landmarks"],
        "莲花山公园": ["lotus hill park shenzhen", "shenzhen park", "china city park"],
        "大梅沙海滨公园": ["dameisha beach shenzhen", "shenzhen beach", "china sandy beach"],
        "华侨城创意文化园": ["oct loft shenzhen", "china creative park", "china art district"],
        "深圳博物馆": ["shenzhen museum", "china museum", "china civic museum"],
        "锦绣中华": ["china folk culture village shenzhen", "china miniature park", "china theme park"],
        "南头古城": ["nantou ancient town shenzhen", "shenzhen old town", "china old village urban"],
    },
    "tianjin": {
        "意式风情区": ["tianjin italian style town", "tianjin old town", "china european style street"],
        "五大道": ["five great avenues tianjin", "tianjin villas", "china european street"],
        "天津之眼": ["tianjin eye ferris wheel", "tianjin ferris wheel", "china ferris wheel night"],
        "古文化街": ["gu wenhua street tianjin", "tianjin old street", "china temple street"],
        "海河游船": ["tianjin hai river cruise", "tianjin river night", "china river night cruise"],
        "天津滨海图书馆": ["tianjin library", "china modern library", "china staircase library"],
        "盘山": ["panshan tianjin", "tianjin mountain temple", "china mountain gate"],
        "相声": ["chinese crosstalk performance", "china teahouse performance", "china folk show"],
    },
    "luoyang": {
        "龙门石窟": ["longmen grottoes", "china buddhist grotto", "china cliff buddha"],
        "洛阳牡丹": ["luoyang peony", "peony flower china", "china peony garden"],
        "白马寺": ["baimasi temple luoyang", "luoyang buddhist temple", "china white horse temple"],
        "应天门": ["yingtian gate luoyang", "luoyang city gate", "china ancient gate night"],
        "丽景门": ["luoyang lijin gate", "china ancient city gate", "luoyang old city"],
        "洛阳博物馆": ["luoyang museum", "china history museum", "china museum"],
        "洛邑古城": ["luoyi ancient town", "china night old street", "china han culture street"],
        "老君山": ["laojun mountain", "china taoist golden peak", "china cloud mountain"],
    },
    "sanya": {
        "亚龙湾": ["yalong bay sanya", "hainan resort beach", "china tropical beach resort"],
        "蜈支洲岛": ["wuzhizhou island", "hainan island", "china island diving"],
        "天涯海角": ["tianya haijiao", "sanya landmark coast", "china coast rock"],
        "南山文化旅游区": ["nanshan temple sanya", "hainan buddhist temple", "china temple sea"],
        "鹿回头": ["luhuitou park sanya", "sanya hill park", "china coastal park"],
        "大东海": ["dadonghai beach sanya", "sanya beach", "china tropical bay"],
        "大小洞天": ["sanya nanshan dongtian", "hainan scenic grotto", "china coastal grotto"],
        "第一市场海鲜": ["sanya first market", "china seafood market", "china fresh seafood"],
    },
    "lasa": {
        "布达拉宫": ["potala palace", "lhasa tibet", "china tibet palace"],
        "大昭寺": ["jokhang temple lhasa", "lhasa monastery", "china tibet monastery"],
        "八廓街": ["barkhor street lhasa", "lhasa old street", "china tibet street"],
        "纳木错": ["namtso lake", "china tibet lake", "china blue lake plateau"],
        "羊卓雍措": ["yamdrok lake", "tibet turquoise lake", "china plateau lake"],
        "色拉寺": ["sera monastery", "lhasa monastery debate", "china tibet monastery"],
        "罗布林卡": ["norbulinka palace", "lhasa palace garden", "china palace garden"],
        "甜茶馆": ["tibetan teahouse", "lhasa tea house", "china teahouse interior"],
    },
    "urumqi": {
        "天山天池": ["tianchi lake tian shan", "xinjiang lake snow mountain", "china turquoise lake"],
        "国际大巴扎": ["urumqi grand bazaar", "xinjiang bazaar", "china market architecture"],
        "红山公园": ["hongshan park urumqi", "urumqi city hill", "china city park red"],
        "南山牧场": ["nanshan pasture urumqi", "xinjiang grassland", "china mountain pasture"],
        "水磨沟公园": ["shuimogou park urumqi", "urumqi park river", "china city park stream"],
        "新疆博物馆": ["xinjiang museum urumqi", "china museum", "china ethnic museum"],
        "红光山": ["hongguangshan urumqi", "urumqi buddhist hill", "china uyghur architecture"],
        "二道桥市场": ["erdaoqiao market urumqi", "xinjiang market", "china dried fruit market"],
    },
    "dunhuang": {
        "莫高窟": ["mogao caves", "dunhuang grottoes", "china buddhist cave mural"],
        "鸣沙山·月牙泉": ["mingsha mountain crescent lake", "dunhuang sand dune", "china desert spring"],
        "玉门关": ["yumen pass", "china silk road fort", "china desert ruin"],
        "雅丹国家地质公园": ["dunhuang yardang", "china yardang landform", "china desert rock formation"],
        "敦煌夜市": ["dunhuang night market", "china night market food", "china street food night"],
        "西千佛洞": ["xian qianfo cave", "dunhuang grotto", "china buddhist cave"],
        "敦煌博物馆": ["dunhuang museum", "china museum", "china silk road museum"],
        "敦煌古城": ["dunhuang ancient city", "china film set old town", "china old town set"],
    },
    "fuzhou": {
        "三坊七巷": ["sanfang qixiang fuzhou", "fuzhou old street", "china ancient lane"],
        "鼓山": ["gushan fuzhou", "fuzhou mountain temple", "china mountain temple"],
        "平潭岛": ["pingtan island fujian", "fujian blue island", "china island coast"],
        "福州西湖": ["fuzhou west lake", "fuzhou lake park", "china lake park"],
        "上下杭": ["shangxiahang fuzhou", "fuzhou historic district", "china merchant house"],
        "烟台山": ["yantai hill fuzhou", "fuzhou hill street", "china hill district"],
        "福州温泉": ["fuzhou hot spring", "china hot spring resort", "china spa pool"],
        "国家森林公园": ["fuzhou forest park", "china forest park", "china subtropical forest"],
    },
}

data = json.load(io.open(TARGET, encoding="utf-8"))
added = updated = 0
for cid, pois in MANUAL.items():
    if cid not in data:
        data[cid] = {}
    for name, queries in pois.items():
        # 景点名可能在知识库里带后缀，做模糊匹配
        key = name
        if key not in data[cid]:
            cands = [k for k in data[cid] if name in k or k in name]
            if cands:
                key = cands[0]
            else:
                added += 1
                data[cid][key] = queries
                continue
        if data[cid][key] != queries:
            data[cid][key] = queries
            updated += 1

with io.open(TARGET, "w", encoding="utf-8") as f:
    f.write(json.dumps(data, ensure_ascii=False, indent=2))

print(f"新增 {added} 条，更新 {updated} 条", file=OUT)
for cid in ("chongqing", "guiyang", "xian"):
    print(f"\n[{cid}]", file=OUT)
    for k, v in list(data[cid].items())[:4]:
        print(f"  {k}: {v}", file=OUT)
OUT.close()
