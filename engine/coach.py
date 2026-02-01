"""
Conversational Coaching Module

Text-based coaching feedback for chess moves.
Provides natural-language explanations based on move quality, game phase,
and material changes. Uses a fixed "Coach" personality.

No gameplay logic changes — purely output/feedback generation.
"""

import random
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

from .game_state import MoveQuality, GamePhase, MaterialBalance


@dataclass
class MoveContext:
    """Context information for generating coaching feedback."""
    move: str
    quality: MoveQuality
    phase: GamePhase
    centipawn_loss: float = 0.0
    material_change: int = 0  # Positive = gained, negative = lost
    is_capture: bool = False
    is_check: bool = False
    piece_moved: str = ""
    best_move: Optional[str] = None


class Coach:
    """
    Text-based conversational chess coach.
    
    Generates concise, natural-language feedback on player moves.
    Uses a fixed encouraging and instructive personality.
    
    Example:
        >>> coach = Coach()
        >>> feedback = coach.comment_on_move(MoveContext(
        ...     move="e2e4",
        ...     quality=MoveQuality.GOOD,
        ...     phase=GamePhase.OPENING
        ... ))
        >>> print(feedback)
        "Good move! Controlling the center early is a solid opening principle."
    """
    
    # =========================================================================
    # MOVE QUALITY FEEDBACK TEMPLATES
    # =========================================================================
    
    BLUNDER_RESPONSES = [
        "Oops, that's a blunder!{reason}",
        "That was a serious mistake.{reason}",
        "Be careful! That move loses significant value.{reason}",
        "That's going to hurt.{reason}",
        "A costly error there.{reason}",
    ]
    
    MISTAKE_RESPONSES = [
        "That's not the best choice here.{reason}",
        "A small mistake.{reason}",
        "You can do better than that.{reason}",
        "Not ideal, but recoverable.{reason}",
        "That weakens your position a bit.{reason}",
    ]
    
    INACCURACY_RESPONSES = [
        "Slight inaccuracy.{reason}",
        "There was a stronger move available.{reason}",
        "A minor slip.{reason}",
        "Not quite optimal.{reason}",
        "Close, but not the best.{reason}",
    ]
    
    GOOD_RESPONSES = [
        "Good move!{reason}",
        "Solid choice.{reason}",
        "Well played.{reason}",
        "That's a nice move.{reason}",
        "Good thinking!{reason}",
    ]
    
    EXCELLENT_RESPONSES = [
        "Excellent move!{reason}",
        "Brilliant! That's the top choice.{reason}",
        "Perfect! That's what the engine recommends.{reason}",
        "Outstanding play!{reason}",
        "You found the best move!{reason}",
    ]
    
    BOOK_RESPONSES = [
        "Standard opening theory.{reason}",
        "A well-known book move.{reason}",
        "Following established opening principles.{reason}",
        "Textbook play.{reason}",
    ]
    
    # =========================================================================
    # PHASE-SPECIFIC TIPS
    # =========================================================================
    
    OPENING_TIPS = [
        "Control the center with pawns and pieces.",
        "Develop your knights before bishops.",
        "Castle early to protect your king.",
        "Don't move the same piece twice in the opening.",
        "Connect your rooks by developing all minor pieces.",
        "Don't bring your queen out too early.",
        "Fight for central squares: e4, d4, e5, d5.",
        "Develop with a purpose — each move should improve your position.",
    ]
    
    MIDDLEGAME_TIPS = [
        "Look for tactical opportunities: forks, pins, skewers.",
        "Keep your pieces active and coordinated.",
        "Create pressure on your opponent's weaknesses.",
        "Think about pawn structure — it defines the position.",
        "Consider piece exchanges carefully.",
        "Control open files with your rooks.",
        "Knights love outposts — squares where they can't be attacked by pawns.",
        "Look for checks, captures, and threats before each move.",
    ]
    
    ENDGAME_TIPS = [
        "Activate your king! It's a fighting piece in the endgame.",
        "Passed pawns must be pushed.",
        "Rooks belong behind passed pawns.",
        "In king and pawn endgames, opposition is key.",
        "Centralize your king in the endgame.",
        "The side with more active pieces usually wins.",
        "Don't rush — calculate carefully in the endgame.",
        "Cut off the enemy king from your passed pawns.",
    ]
    
    # =========================================================================
    # MATERIAL COMMENTARY
    # =========================================================================
    
    GAINED_MATERIAL = [
        "Nice! You won material.",
        "Good capture — you're up in material now.",
        "You picked up some material there.",
    ]
    
    LOST_MATERIAL = [
        "You lost material on that exchange.",
        "That cost you some material.",
        "Be careful — you're down material now.",
    ]
    
    SACRIFICE_COMMENTS = [
        "A bold sacrifice!",
        "Interesting sacrifice — let's see if it pays off.",
        "Giving up material for activity.",
    ]
    
    # =========================================================================
    # GAME EVENTS
    # =========================================================================
    
    CHECK_COMMENTS = [
        "Check!",
        "You're putting pressure on the king.",
        "Nice check!",
    ]
    
    CHECKMATE_WIN = [
        "Checkmate! Well played!",
        "That's checkmate! Great game!",
        "You got them! Checkmate!",
    ]
    
    CHECKMATE_LOSS = [
        "Checkmate. Better luck next time!",
        "You got checkmated. Let's review what went wrong.",
        "That's checkmate against you. Keep practicing!",
    ]
    
    DRAW_COMMENTS = [
        "The game is a draw. A hard-fought battle!",
        "It's a draw. Neither side could break through.",
        "Draw! Sometimes that's the right result.",
    ]
    
    # =========================================================================
    # CORE METHODS
    # =========================================================================
    
    # =========================================================================
    # PERSONALITY TEMPLATES
    # =========================================================================
    
    # Supportive (Default) - Encouraging, balanced
    SUPPORTIVE_TEMPLATES = {
        "blunder": [
            "Oops, that's a blunder!{reason}",
            "That was a mistake, but we can recover.{reason}",
            "Be careful! That move loses material.{reason}",
        ],
        "good": [
            "Good move!{reason}",
            "Solid choice.{reason}",
            "Well played.{reason}",
        ]
    }
    
    # Empathetic (Frustrated) - Calming, de-escalating
    EMPATHETIC_TEMPLATES = {
        "blunder": [
            "That's tough. Take a deep breath.{reason}",
            "It happens to everyone. Let's focus on the next move.{reason}",
            "Don't worry about that mistake. Reset and focus.{reason}",
        ],
        "good": [
            "Nice recovery!{reason}",
            "Great, you're back on track.{reason}",
            "Steady play. That helps stabilize things.{reason}",
        ]
    }
    
    # Enthusiastic (Confident) - High energy, hype
    ENTHUSIASTIC_TEMPLATES = {
        "blunder": [
            "Whoops! Even champions miss those.{reason}",
            "A rare slip up! You'll get it back.{reason}",
            "Ah! A missed opportunity. Keep the energy up!{reason}",
        ],
        "good": [
            "Yes! Crushing it!{reason}",
            "You are on fire!{reason}",
            "Brilliant! Keep attacking!{reason}",
        ]
    }
    
    # Engaging (Disengaged) - Questioning, re-engaging
    ENGAGING_TEMPLATES = {
        "blunder": [
            "Wait, look closely... see why that's a blunder?{reason}",
            "Hold on, what did we miss there?{reason}",
            "Let's pause. Can you spot the tactical error?{reason}",
        ],
        "good": [
            "There we go! You're focused now.{reason}",
            "Nice one. What's your plan after this?{reason}",
            "Good. Now, how do we follow up?{reason}",
        ]
    }

    # =========================================================================
    # CORE METHODS
    # =========================================================================
    
    def __init__(self, emotion_model: Optional[Any] = None):
        """
        Initialize the Coach.
        
        Args:
            emotion_model: Optional EmotionModel instance.
        """
        self.emotion_model = emotion_model
    
    def comment_on_move(self, context: MoveContext) -> str:
        """
        Generate coaching feedback for a player move.
        
        Args:
            context: MoveContext with move details.
        
        Returns:
            Natural-language coaching feedback string.
        """
        parts = []
        
        # Primary feedback based on move quality
        quality_feedback = self._get_quality_feedback(context)
        parts.append(quality_feedback)
        
        # Add phase-specific color if space permits
        if context.quality in (MoveQuality.GOOD, MoveQuality.EXCELLENT):
            phase_note = self._get_phase_note(context.phase, brief=True)
            if phase_note:
                parts.append(phase_note)
        
        # Material commentary for significant changes
        if abs(context.material_change) >= 3:
            material_note = self._get_material_comment(context.material_change)
            if material_note:
                parts.append(material_note)
        
        # Combine and return
        return " ".join(parts)
    
    def _get_quality_feedback(self, context: MoveContext) -> str:
        """Get feedback template based on move quality and personality."""
        reason = self._generate_reason(context)
        
        # 1. Determine personality
        personality_key = "supportive"
        if self.emotion_model:
            # We import locally to avoid circular imports if needed, 
            # or rely on the object having a .value property
            p = self.emotion_model.get_personality()
            personality_key = p.value
            
        # 2. Select template set
        template_set = self.SUPPORTIVE_TEMPLATES
        if personality_key == "empathetic":
            template_set = self.EMPATHETIC_TEMPLATES
        elif personality_key == "enthusiastic":
            template_set = self.ENTHUSIASTIC_TEMPLATES
        elif personality_key == "engaging":
            template_set = self.ENGAGING_TEMPLATES
            
        # 3. Select specific template
        if context.quality in (MoveQuality.BLUNDER, MoveQuality.MISTAKE):
            options = template_set["blunder"]
        else:
            options = template_set["good"]
            
        # Fallback to standard arrays for specific qualities if needed
        # (For simplicity, we map quality broadly to "good" or "blunder" buckets for personality)
        # But we can mix in the original granular templates
        
        if context.quality in (MoveQuality.INACCURACY, MoveQuality.BOOK):
             # Use standard templates for neutral moves
             return super()._get_quality_feedback(context) if hasattr(super(), '_get_quality_feedback') else self._standard_feedback(context, reason)

        template = random.choice(options)
        return template.format(reason=reason)

    def _standard_feedback(self, context: MoveContext, reason: str) -> str:
        """Fallback to standard templates."""
        templates = {
            MoveQuality.INACCURACY: self.INACCURACY_RESPONSES,
            MoveQuality.BOOK: self.BOOK_RESPONSES,
            MoveQuality.GOOD: self.GOOD_RESPONSES, # Fallback
            MoveQuality.EXCELLENT: self.EXCELLENT_RESPONSES, # Fallback
        }
        options = templates.get(context.quality, self.GOOD_RESPONSES)
        template = random.choice(options)
        return template.format(reason=reason)

    def _generate_reason(self, context: MoveContext) -> str:
        """Generate contextual reason/explanation."""
        reasons = []
        
        # For blunders/mistakes, mention what was lost
        if context.quality in (MoveQuality.BLUNDER, MoveQuality.MISTAKE):
            if context.material_change < 0:
                if context.material_change <= -9:
                    reasons.append(" You lost your queen!")
                elif context.material_change <= -5:
                    reasons.append(" You lost a rook!")
                elif context.material_change <= -3:
                    reasons.append(" You lost a piece!")
                else:
                    reasons.append(" You lost material.")
            elif context.best_move:
                reasons.append(f" {context.best_move} was better.")
            else:
                reasons.append("")
        
        # For good moves, add encouragement
        elif context.quality in (MoveQuality.GOOD, MoveQuality.EXCELLENT):
            if context.is_check:
                reasons.append(" Creating threats!")
            elif context.is_capture and context.material_change > 0:
                reasons.append(" Nice capture!")
            elif context.phase == GamePhase.OPENING:
                reasons.append(" Developing nicely.")
            else:
                reasons.append("")
        
        else:
            reasons.append("")
        
        return reasons[0] if reasons else ""
    
    def _get_phase_note(self, phase: GamePhase, brief: bool = False) -> str:
        """Get a brief phase-appropriate note."""
        if phase == GamePhase.OPENING:
            notes = [
                "Keep developing!",
                "Good opening play.",
                "Fight for the center.",
            ]
        elif phase == GamePhase.MIDDLEGAME:
            notes = [
                "Look for tactics!",
                "Keep the pressure on.",
                "Stay alert for combinations.",
            ]
        else:  # Endgame
            notes = [
                "Technique is key now.",
                "Activate your king!",
                "Push those pawns.",
            ]
        
        return random.choice(notes) if random.random() > 0.5 else ""
    
    def _get_material_comment(self, change: int) -> str:
        """Get comment based on material change."""
        if change >= 3:
            return random.choice(self.GAINED_MATERIAL)
        elif change <= -3:
            return random.choice(self.LOST_MATERIAL)
        return ""
    
    def opening_tip(self) -> str:
        """Get a random opening tip."""
        return f"💡 Tip: {random.choice(self.OPENING_TIPS)}"
    
    def middlegame_tip(self) -> str:
        """Get a random middlegame tip."""
        return f"💡 Tip: {random.choice(self.MIDDLEGAME_TIPS)}"
    
    def endgame_tip(self) -> str:
        """Get a random endgame tip."""
        return f"💡 Tip: {random.choice(self.ENDGAME_TIPS)}"
    
    def get_phase_tip(self, phase: GamePhase) -> str:
        """Get a tip appropriate for the current phase."""
        if phase == GamePhase.OPENING:
            return self.opening_tip()
        elif phase == GamePhase.MIDDLEGAME:
            return self.middlegame_tip()
        else:
            return self.endgame_tip()
    
    def comment_on_check(self) -> str:
        """Get a comment for when player gives check."""
        return random.choice(self.CHECK_COMMENTS)
    
    def comment_on_checkmate(self, player_won: bool) -> str:
        """Get a comment for checkmate."""
        if player_won:
            return random.choice(self.CHECKMATE_WIN)
        else:
            return random.choice(self.CHECKMATE_LOSS)
    
    def comment_on_draw(self, reason: str = "") -> str:
        """Get a comment for draw."""
        base = random.choice(self.DRAW_COMMENTS)
        if reason:
            return f"{base} ({reason})"
        return base
    
    def profile_tip(self, strengths: List[str], weaknesses: List[str]) -> str:
        """
        Get a personalized tip based on player profile.
        
        Args:
            strengths: List of player strengths.
            weaknesses: List of player weaknesses.
        """
        if not weaknesses and not strengths:
            return self.encourage()
        
        # Address weaknesses first
        if weaknesses and random.random() < 0.7:
            weakness = random.choice(weaknesses)
            if "Opening" in weakness:
                return f"💡 Coach Tip: {random.choice(self.OPENING_TIPS)}"
            elif "Endgame" in weakness:
                return f"💡 Coach Tip: {random.choice(self.ENDGAME_TIPS)}"
            elif "Blunders" in weakness:
                return "💡 Coach Tip: Take an extra moment to check for hanging pieces before every move."
            elif "Passive" in weakness:
                return "💡 Coach Tip: Look for ways to improve your piece activity. Passive play leads to difficult positions."
        
        # Reinforce strengths
        if strengths:
            strength = random.choice(strengths)
            if "Endgame" in strength:
                return "💡 You're strong in the endgame - try to simplify the position!"
            elif "Tactical" in strength:
                return "💡 Look for complex tactical lines - that's where you shine!"
            elif "Opening" in strength:
                return "💡 Your openings are solid. Use that advantage to build a strong middlegame plan."
            
        return self.encourage()
    
    def game_summary(
        self,
        result: str,
        total_moves: int,
        blunders: int,
        mistakes: int,
        excellent_moves: int,
        accuracy: float
    ) -> str:
        """
        Generate an end-of-game summary.
        
        Args:
            result: "win", "loss", or "draw"
            total_moves: Total moves played
            blunders: Number of blunders
            mistakes: Number of mistakes
            excellent_moves: Number of excellent moves
            accuracy: Accuracy percentage
        
        Returns:
            Multi-line game summary string.
        """
        lines = []
        lines.append("=" * 40)
        lines.append("📊 GAME SUMMARY")
        lines.append("=" * 40)
        
        # Result
        if result == "win":
            lines.append("🎉 Result: Victory!")
        elif result == "loss":
            lines.append("😔 Result: Defeat")
        else:
            lines.append("🤝 Result: Draw")
        
        # Stats
        lines.append(f"📈 Accuracy: {accuracy:.1f}%")
        lines.append(f"🎯 Total moves: {total_moves}")
        lines.append(f"⭐ Excellent moves: {excellent_moves}")
        
        if blunders > 0:
            lines.append(f"❌ Blunders: {blunders}")
        if mistakes > 0:
            lines.append(f"⚠️ Mistakes: {mistakes}")
        
        # Coaching note
        lines.append("")
        if accuracy >= 90:
            lines.append("🏆 Outstanding performance! You played like a master.")
        elif accuracy >= 75:
            lines.append("👍 Good game! Keep practicing to reduce those small errors.")
        elif accuracy >= 60:
            lines.append("📚 Decent effort. Focus on calculating a bit deeper before each move.")
        else:
            lines.append("💪 Keep at it! Review your blunders to learn from them.")
        
        lines.append("=" * 40)
        
        return "\n".join(lines)
    
    def encourage(self) -> str:
        """Get a random encouragement message."""
        encouragements = [
            "You've got this!",
            "Keep thinking ahead.",
            "Stay focused!",
            "Trust your instincts.",
            "Every move is a chance to learn.",
            "Chess is a journey — enjoy the game!",
        ]
        return random.choice(encouragements)
