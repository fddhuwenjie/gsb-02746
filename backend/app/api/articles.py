from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models.article import Article

router = APIRouter()


class ArticleResponse(BaseModel):
    id: int
    title: str
    author: Optional[str]
    content: Optional[str]
    source: Optional[str]
    issue: Optional[str]
    year: Optional[int]
    month: Optional[int]
    category: Optional[str]
    file_path: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ArticleListResponse(BaseModel):
    items: List[ArticleResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=ArticleListResponse)
async def get_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    year: Optional[str] = None,
    month: Optional[str] = None,
    issue: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Article)

    def _clean(v):
        if v is None:
            return None
        v = v.strip()
        return v if v else None

    year_v = _clean(year)
    month_v = _clean(month)
    issue_v = _clean(issue)
    category_v = _clean(category)
    search_v = _clean(search)

    if year_v is not None:
        try:
            year_i = int(year_v)
        except ValueError:
            raise HTTPException(status_code=422, detail="year must be an integer")
        query = query.filter(Article.year == year_i)
    if month_v is not None:
        try:
            month_i = int(month_v)
        except ValueError:
            raise HTTPException(status_code=422, detail="month must be an integer")
        query = query.filter(Article.month == month_i)
    if issue_v:
        query = query.filter(Article.issue == issue_v)
    if category_v:
        query = query.filter(Article.category == category_v)
    if search_v:
        query = query.filter(or_(
            Article.title.contains(search_v),
            Article.author.contains(search_v),
        ))
    
    total = query.count()
    items = (
        query
        .order_by(desc(Article.created_at), desc(Article.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    
    return ArticleListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/issues")
async def get_issues(db: Session = Depends(get_db)):
    results = db.query(Article.year, Article.month, Article.issue).distinct().all()
    issues = [{"year": r[0], "month": r[1], "issue": r[2]} for r in results if r[0]]
    return sorted(issues, key=lambda x: (x["year"] or 0, x["month"] or 0), reverse=True)


@router.get("/categories")
async def get_categories(db: Session = Depends(get_db)):
    results = db.query(Article.category).distinct().all()
    return [r[0] for r in results if r[0]]


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: Session = Depends(get_db)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    return article


@router.delete("/{article_id}")
async def delete_article(article_id: int, db: Session = Depends(get_db)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    db.delete(article)
    db.commit()
    return {"message": "删除成功"}


@router.post("/seed")
async def seed_test_data(db: Session = Depends(get_db)):
    """添加测试数据"""
    test_articles = [
        {"title": "人生的意义", "author": "张三", "content": "人生的意义不在于你拥有多少，而在于你给予了多少。每一个清晨醒来，都是生命给予我们的礼物。我们应该珍惜每一天，用心去感受生活中的美好。\n\n有人说，人生就像一场旅行，重要的不是目的地，而是沿途的风景。这话说得很有道理。我们常常为了追求某个目标而忽略了身边的美好，等到回首往事时，才发现最珍贵的时光已经悄然流逝。\n\n所以，让我们放慢脚步，用心去感受每一个当下。无论是清晨的第一缕阳光，还是傍晚的最后一抹晚霞，都值得我们驻足欣赏。", "source": "读者", "issue": "第1期", "year": 2024, "month": 1, "category": "人生感悟"},
        {"title": "读书的乐趣", "author": "李四", "content": "书籍是人类进步的阶梯，这句话我们从小就听过。但真正体会到读书的乐趣，却需要我们静下心来，沉浸在文字的世界里。\n\n一本好书，就像一位智者，在你迷茫时给你指引，在你困惑时给你答案。它不会因为你的身份地位而改变态度，也不会因为时间的流逝而失去价值。\n\n我喜欢在安静的夜晚，泡一杯清茶，翻开一本书，让思绪随着文字飘向远方。那种感觉，就像是在与作者进行一场跨越时空的对话。", "source": "读者", "issue": "第1期", "year": 2024, "month": 1, "category": "读书"},
        {"title": "母亲的手", "author": "王五", "content": "母亲的手，是我见过最美的手。那双手，曾经白皙细嫩，如今却布满了岁月的痕迹。\n\n小时候，母亲的手牵着我学走路；上学时，母亲的手为我整理书包；长大后，母亲的手依然在为我操劳。那双手，做过无数顿饭菜，洗过无数件衣服，却从未有过一句抱怨。\n\n如今，我已经长大成人，而母亲的手却越来越苍老。每次回家，我都想握住那双手，告诉她：妈妈，您辛苦了。", "source": "读者", "issue": "第2期", "year": 2024, "month": 1, "category": "亲情"},
        {"title": "时间的价值", "author": "赵六", "content": "时间是最公平的，它给每个人每天都是24小时。但时间又是最不公平的，因为它给每个人的价值却大不相同。\n\n有人用时间创造了伟大的事业，有人用时间虚度了宝贵的年华。时间不会因为你的懈怠而停下脚步，也不会因为你的努力而多给你一分一秒。\n\n所以，珍惜时间吧。把每一天都当作生命中的最后一天来过，你会发现，生活原来可以如此充实和美好。", "source": "读者", "issue": "第1期", "year": 2024, "month": 2, "category": "人生感悟"},
        {"title": "友情的真谛", "author": "孙七", "content": "什么是真正的友情？我想，真正的友情不是锦上添花，而是雪中送炭。\n\n真正的朋友，不会因为你的成功而嫉妒，也不会因为你的失败而离开。他们会在你得意时给你提醒，在你失意时给你鼓励。\n\n人生得一知己足矣。如果你身边有这样的朋友，请好好珍惜。因为在这个世界上，真正懂你的人，真的不多。", "source": "读者", "issue": "第2期", "year": 2024, "month": 2, "category": "友情"},
        {"title": "春天的故事", "author": "周八", "content": "春天来了，万物复苏。小草从土里探出头来，花儿竞相开放，鸟儿在枝头歌唱。\n\n我喜欢春天，不仅因为它的美丽，更因为它代表着希望和新生。无论过去的冬天多么寒冷，春天总会如期而至。\n\n人生也是如此。无论你现在经历着怎样的困难，请相信，春天一定会来。只要你不放弃希望，生活就会给你惊喜。", "source": "读者", "issue": "第1期", "year": 2024, "month": 3, "category": "散文"},
        {"title": "坚持的力量", "author": "吴九", "content": "成功的秘诀是什么？很多人都在寻找答案。其实，答案很简单，那就是坚持。\n\n坚持，说起来容易，做起来难。多少人在成功的前一刻选择了放弃，多少人在黎明前的黑暗中迷失了方向。\n\n但那些最终成功的人，都有一个共同的特点：他们从不轻言放弃。即使跌倒了，也会爬起来继续前行。因为他们知道，只要坚持，就一定能看到胜利的曙光。", "source": "读者", "issue": "第2期", "year": 2024, "month": 3, "category": "励志"},
        {"title": "简单生活", "author": "郑十", "content": "在这个物欲横流的时代，我们常常被各种欲望所困扰。我们想要更大的房子，更好的车子，更多的金钱。但当我们拥有了这些之后，真的就幸福了吗？\n\n其实，幸福很简单。一顿可口的饭菜，一次愉快的交谈，一个温暖的拥抱，都能让我们感到幸福。\n\n学会简单生活吧。放下那些不必要的欲望，你会发现，生活原来可以如此轻松和美好。", "source": "读者", "issue": "第1期", "year": 2024, "month": 4, "category": "生活"},
    ]
    
    for article_data in test_articles:
        article = Article(**article_data)
        db.add(article)
    db.commit()
    
    return {"message": f"已添加 {len(test_articles)} 篇测试文章"}
