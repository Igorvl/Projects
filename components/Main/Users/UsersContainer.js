// import React from 'react';
import {followAC, getUsersAC, unfollowAC, totalPagesAC, choosedPageAC} from "../../Redux/usersReducer";
import {connect} from "react-redux";
// import Users from "./Users";
// import UsersC from "./UsersC";
import UsersH from "./UsersH";

const mapStateToProps = (state) => {
	return ({
		usersData: state.usersPage.usersData,
		totalPages: state.usersPage.totalPages,
		currentPage: state.usersPage.currentPage,
		choosedPage: state.usersPage.choosedPage,
		usersOnPage: state.usersPage.usersOnPage,
	})
};
const mapDispatchToProps = (dispatch) => {
	return (
		{
			// callbacks for buttons from Users
			followCB: userId => dispatch(followAC(userId)),
			unfollowCB: userId => dispatch(unfollowAC(userId)),
			getUsersCB: usersData => dispatch(getUsersAC(usersData)),
			totalPagesCB: totalPages => dispatch(totalPagesAC(totalPages)),
			choosedPageCB: choosedPage => dispatch(choosedPageAC(choosedPage)),
		}
	)
};
export default connect(mapStateToProps, mapDispatchToProps)(UsersH);
// export default connect(mapStateToProps, mapDispatchToProps)(UsersC);

