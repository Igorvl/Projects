// import React from 'react';
import {addNewComment, addNewCommentText} from "../../Redux/dialogsReducer";
import Dialogs from "./Dialogs";
import {connect} from "react-redux";

const mapStateToProps = (state) => {
	return ({
		// data from (redux-store)-state for Dialogs. Default values defined in redux-store and dialogReducer
		dialogData: state.dialogsPage.dialogData,
		messageData: state.dialogsPage.messageData,
		newCommentTxt: state.dialogsPage.newCommentTxt,
		isLoggedIn: state.auth.isLoggedIn,
	})
};
const mapDispatchToProps = (dispatch) => {
	return (
		{
			// callbacks for textarea and button from Dialog
			addNewCommentTextCB: txt =>	dispatch(addNewCommentText(txt)),
			addNewCommentCB: () => dispatch(addNewComment()),
		}
	)
};
export default connect(mapStateToProps, mapDispatchToProps)(Dialogs);

