import chess
import pygame
import sys
import os
import chess.engine
from pygame.locals import *

# ------------ 실행 경로 설정 (EXE에서도 동작) ------------
def resource_path(relative_path):
    """PyInstaller EXE 실행 시와 개발 환경 모두에서 리소스 경로를 반환합니다."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# ------------ 기본 설정 ------------
WIDTH, HEIGHT = 800, 640
BOARD_SIZE = 640            # 체스판 영역 폭(픽셀)
SQUARE_SIZE = BOARD_SIZE // 8
WHITE = (255, 255, 255)
BLACK = (100, 100, 100)
GREEN = (0, 200, 0)
HIGHLIGHT = (255, 215, 0)
GRAY = (200, 200, 200)
BG = (18, 18, 18)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("체스 게임")
# 글꼴: 기물 유니코드 폰트(이미지 없을 때 폴백)
piece_font = pygame.font.SysFont(None, SQUARE_SIZE - 10)
ui_font = pygame.font.SysFont(None, 20)
clock = pygame.time.Clock()

# ------------ 이미지 로딩 (PNG 기반) ------------
PIECE_IMAGES = {}
PIECE_TYPES = ['p', 'r', 'n', 'b', 'q', 'k']
missing_images = []
for color in ['w', 'b']:
    for piece in PIECE_TYPES:
        symbol = piece.upper() if color == 'w' else piece
        image_path = resource_path(f"images/{color}{piece}.png")
        if os.path.exists(image_path):
            try:
                img = pygame.image.load(image_path).convert_alpha()
                PIECE_IMAGES[symbol] = pygame.transform.smoothscale(img, (SQUARE_SIZE, SQUARE_SIZE))
            except Exception as e:
                print(f"이미지 로드 실패: {image_path} -> {e}")
                PIECE_IMAGES[symbol] = None
                missing_images.append(image_path)
        else:
            PIECE_IMAGES[symbol] = None
            missing_images.append(image_path)

if missing_images:
    print("⚠ 이미지 파일이 일부 누락되었거나 로드에 실패했습니다.")
    print("누락 예:")
    for p in missing_images[:10]:
        print("  ", p)
    print("=> images 폴더(프로젝트 또는 EXE에 포함)에 png 파일이 있는지 확인하세요.")

# 유니코드 폰트용 기호(이미지 없을 때 표시)
UNICODE_PIECES = {
    'r': '♜', 'n': '♞', 'b': '♝', 'q': '♛', 'k': '♚', 'p': '♟',
    'R': '♖', 'N': '♘', 'B': '♗', 'Q': '♕', 'K': '♔', 'P': '♙',
}

# ------------ 보드 초기화 ------------
board = chess.Board()
selected_square = None
legal_moves = []
move_stack = []

# ------------ 엔진 설정 (Stockfish) ------------
engine = None
engine_path = resource_path(os.path.join("stockfish", "stockfish-windows-x86-64-avx2.exe"))
if not os.path.exists(engine_path):
    # 다른 흔한 이름도 시도해봄
    alt = resource_path(os.path.join("stockfish", "stockfish.exe"))
    if os.path.exists(alt):
        engine_path = alt

try:
    if os.path.exists(engine_path):
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    else:
        engine = None
        print("⚠️ Stockfish 엔진 파일을 찾을 수 없습니다. 승률/분석 기능 비활성화됩니다.")
except Exception as e:
    engine = None
    print("엔진 실행 중 오류:", e)

# ------------ 평가(승률) 관련 캐시 ------------
_last_eval_fen = None
_last_winrate = 0.5

def compute_winrate():
    global _last_eval_fen, _last_winrate
    try:
        if not engine:
            _last_winrate = 0.5
            _last_eval_fen = board.fen()
            return _last_winrate
        fen = board.fen()
        if fen == _last_eval_fen:
            return _last_winrate
        info = engine.analyse(board, chess.engine.Limit(time=0.05))
        score = info.get("score")
        if score is None:
            _last_winrate = 0.5
        else:
            rel = score.relative
            if rel.is_mate():
                # 매트: 숫자가 양수면 백 유리
                _last_winrate = 1.0 if rel.mate() > 0 else 0.0
            else:
                cp = rel.score() or 0
                # -300..+300 -> 0..1 (단순 정규화)
                _last_winrate = max(min((cp + 300) / 600.0, 1.0), 0.0)
        _last_eval_fen = fen
        return _last_winrate
    except Exception as e:
        print("엔진 분석 오류:", e)
        _last_winrate = 0.5
        _last_eval_fen = board.fen()
        return _last_winrate

# ------------ 보드/렌더링 함수 ------------

def draw_board():
    # 체스판 그리기
    light = (240, 217, 181)
    dark = (181, 136, 99)
    for r in range(8):
        for f in range(8):
            color = light if (r + f) % 2 == 0 else dark
            rect = pygame.Rect(f * SQUARE_SIZE, r * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE)
            pygame.draw.rect(screen, color, rect)
            sq = chess.square(f, 7 - r)
            piece = board.piece_at(sq)
            if piece:
                sym = piece.symbol()
                img = PIECE_IMAGES.get(sym)
                if img:
                    screen.blit(img, rect.topleft)
                else:
                    glyph = UNICODE_PIECES.get(sym, '?')
                    text = piece_font.render(glyph, True, (0, 0, 0))
                    tr = text.get_rect(center=rect.center)
                    screen.blit(text, tr)

    # 선택한 칸 강조
    if selected_square is not None:
        sf = chess.square_file(selected_square)
        sr = 7 - chess.square_rank(selected_square)
        sel_rect = pygame.Rect(sf * SQUARE_SIZE, sr * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE)
        pygame.draw.rect(screen, HIGHLIGHT, sel_rect, 3)

    # 가능한 이동 강조
    for mv in legal_moves:
        if mv.from_square == selected_square:
            to_sq = mv.to_square
            tf = chess.square_file(to_sq)
            tr = 7 - chess.square_rank(to_sq)
            center = (tf * SQUARE_SIZE + SQUARE_SIZE // 2, tr * SQUARE_SIZE + SQUARE_SIZE // 2)
            pygame.draw.circle(screen, GREEN, center, 8)


def draw_winrate_bar(winrate):
    # 오른쪽에 승률 막대 표시
    bar_x = BOARD_SIZE + 20
    bar_y = 20
    bar_w = 30
    bar_h = HEIGHT - 40
    pygame.draw.rect(screen, GRAY, (bar_x, bar_y, bar_w, bar_h))
    white_h = int(bar_h * winrate)
    pygame.draw.rect(screen, (255, 255, 255), (bar_x, bar_y, bar_w, white_h))
    pygame.draw.rect(screen, (40, 40, 40), (bar_x, bar_y + white_h, bar_w, bar_h - white_h))
    # 퍼센트 텍스트
    txt = ui_font.render(f"White: {int(winrate*100)}%", True, (255,255,255))
    screen.blit(txt, (bar_x - 10, bar_y + bar_h + 5))


def get_square_under_mouse(pos):
    x, y = pos
    if x < 0 or x >= BOARD_SIZE or y < 0 or y >= BOARD_SIZE:
        return None
    file = x // SQUARE_SIZE
    rank = 7 - (y // SQUARE_SIZE)
    return chess.square(file, rank)


def prompt_promotion(color_is_white):
    # 승진 선택 UI (우측 영역에 표시)
    options = ['q', 'r', 'b', 'n']
    rects = []
    base_x = BOARD_SIZE + 20
    base_y = 40
    for i, p in enumerate(options):
        rect = pygame.Rect(base_x, base_y + i * (SQUARE_SIZE // 2 + 10), SQUARE_SIZE // 2, SQUARE_SIZE // 2)
        pygame.draw.rect(screen, GRAY, rect)
        key = p.upper() if color_is_white else p
        img = PIECE_IMAGES.get(key)
        if img:
            img_s = pygame.transform.smoothscale(img, (rect.w, rect.h))
            screen.blit(img_s, rect.topleft)
        else:
            glyph = UNICODE_PIECES.get(key, '?')
            text = piece_font.render(glyph, True, (0,0,0))
            tr = text.get_rect(center=rect.center)
            screen.blit(text, tr)
        rects.append((rect, p))
    pygame.display.flip()

    # 클릭 대기
    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
            if event.type == MOUSEBUTTONDOWN:
                for rect, piece in rects:
                    if rect.collidepoint(event.pos):
                        return piece
            if event.type == KEYDOWN:
                # 키로도 선택 가능: q/r/b/n
                if event.unicode.lower() in ['q','r','b','n']:
                    return event.unicode.lower()
        clock.tick(30)


def try_make_move(from_sq, to_sq):
    """승진 처리 포함해서 실제로 수를 두려고 시도합니다. 성공하면 True 반환."""
    piece = board.piece_at(from_sq)
    if piece is None:
        return False
    # 승진 검사: 폰이 마지막 랭크로 이동하는 경우
    if piece.piece_type == chess.PAWN and chess.square_rank(to_sq) in (0, 7):
        color_white = piece.color == chess.WHITE
        prom = prompt_promotion(color_white)
        prom_map = {'q': chess.QUEEN, 'r': chess.ROOK, 'b': chess.BISHOP, 'n': chess.KNIGHT}
        move = chess.Move(from_sq, to_sq, promotion=prom_map.get(prom, chess.QUEEN))
    else:
        move = chess.Move(from_sq, to_sq)

    if move in board.legal_moves:
        board.push(move)
        move_stack.append(move)
        return True
    return False

# ------------ 메인 루프 ------------
running = True
while running:
    screen.fill(BG)
    draw_board()
    winrate = compute_winrate()
    draw_winrate_bar(winrate)

    pygame.display.flip()

    for event in pygame.event.get():
        if event.type == QUIT:
            running = False
            break
        elif event.type == KEYDOWN:
            if event.key == K_u and move_stack:
                board.pop()
                move_stack.pop()
                # 평가 캐시 초기화
                _last_eval_fen = None
            elif event.key == K_ESCAPE:
                running = False
                break
        elif event.type == MOUSEBUTTONDOWN:
            sq = get_square_under_mouse(event.pos)
            if sq is None:
                # 우측 영역 클릭은 무시(또는 UI 버튼용으로 사용 가능)
                continue
            if selected_square is None:
                piece = board.piece_at(sq)
                if piece and piece.color == board.turn:
                    selected_square = sq
                    legal_moves = list(board.legal_moves)
            else:
                made = try_make_move(selected_square, sq)
                selected_square = None
                legal_moves = []
                if made:
                    # 평가 캐시 초기화(새로운 보드 상태 분석 필요)
                    _last_eval_fen = None

    clock.tick(30)

# 종료 처리
if engine:
    try:
        engine.quit()
    except Exception:
        pass
pygame.quit()
sys.exit()